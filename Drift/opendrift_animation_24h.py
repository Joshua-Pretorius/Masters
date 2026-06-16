#!/usr/bin/env python
"""
OpenDrift 24-hour Animation for Marine Plastics
===============================================
Extended simulation over 24+ hours with focused visualization on ~20 km² area
Seeding particles from detected marine debris locations in shapefiles
"""

from datetime import timedelta
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.animation import FuncAnimation
from pathlib import Path
import re
from datetime import datetime, timedelta
import xarray as xr
import rioxarray as rxr
from opendrift.models.plastdrift import PlastDrift
from opendrift.readers import reader_netCDF_CF_generic
import geopandas as gpd
import pandas as pd
import time
import os
from pyproj import Transformer

def get_third_date_folder():
    """Get the third date folder in the drift directory"""
    drift_dir = Path(".")
    date_dirs = sorted([d for d in drift_dir.iterdir() if d.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', d.name)])
    if len(date_dirs) < 3:
        raise ValueError("Less than 3 date directories found!")
    return date_dirs[2]  # Return the third date folder

def parse_scene_from_ref(date_dir: Path):
    """Return (ref_path, tile, date_iso) from S2 B02 filename S2_<TILE>_<YYYY-MM-DD>_B02.tif"""
    ref = next((date_dir/"optical").glob("S2_*_B02.tif"))
    m = re.search(r"S2_([0-9A-Z]{5})_(\d{4}-\d{2}-\d{2})_B02\.tif$", ref.name, re.I)
    if not m:
        raise ValueError(f"Unexpected S2 ref name: {ref.name}")
    tile, date_iso = m.group(1), m.group(2)
    return ref, tile.upper(), date_iso

def find_matching_shp(shp_root: Path, tile: str, date_iso: str):
    """Find shapefile matching the scene. Shapefiles look like: S2_<DD-M-YY>_<TILE>.shp"""
    def _iso_from_ddmmyy(d, m, y2):
        y = 2000 + int(y2)  # assume 20xx
        from datetime import date
        return date(y, int(m), int(d)).isoformat()
    
    cands = list(shp_root.glob(f"S2_*_{tile}.shp"))
    for p in cands:
        mm = re.search(r"S2_(\d{1,2})-(\d{1,2})-(\d{2})_"+re.escape(tile)+r"\.shp$", p.name, re.I)
        if not mm: 
            continue
        d,m,y = mm.groups()
        if _iso_from_ddmmyy(d,m,y) == date_iso:
            return p
    return None

def seeds_wgs84_from_shp(shp_path: Path):
    """Extract seed coordinates from shapefile (from OpenDriftFinal notebook logic)"""
    gdf = gpd.read_file(shp_path)
    gdf = gdf[gdf.get("id", 0) == 1].copy()  # Only features with id==1
    if gdf.empty:
        return [], []
    
    reps = []
    for g in gdf.geometry:
        if g.geom_type == "Point": 
            reps.append(g)
        elif g.geom_type in ("Polygon","MultiPolygon"): 
            reps.append(g.representative_point())
        else: 
            reps.append(g.centroid)
    
    g2 = gpd.GeoDataFrame(geometry=reps, crs=gdf.crs).to_crs(4326)
    return [p.x for p in g2.geometry], [p.y for p in g2.geometry]

# Helper functions for forcing file generation
def _open_match(p: Path, ref):
    """Open and reproject raster to match reference"""
    da = rxr.open_rasterio(p).squeeze(drop=True)
    return da.rio.reproject_match(ref)

def _dec(v, step):
    """Decimate for speed"""
    return v.isel(y=slice(None,None,step), x=slice(None,None,step)).astype("float32")

def _atomic_netcdf_write(ds: xr.Dataset, out_nc: Path):
    """Atomic write of NetCDF file"""
    tmp = out_nc.with_suffix(out_nc.suffix + f".tmp.{int(time.time())}")
    ds.to_netcdf(tmp, mode="w", engine="netcdf4")
    ds.close()
    if out_nc.exists():
        try:
            os.remove(out_nc)
        except PermissionError:
            time.sleep(0.5)
            try: os.remove(out_nc)
            except Exception: pass
    os.replace(str(tmp), str(out_nc))

def get_optical_ref(date_dir: Path) -> Path:
    """Get optical reference file"""
    opt = date_dir/"optical"
    ref_file = next(opt.glob("S2_*_B02.tif"), None)
    if ref_file is None:
        raise FileNotFoundError(f"No S2 B02 reference file found in {opt}")
    return ref_file

def build_plast_forcing(date_dir: Path, sar_dir: Path, decimate: int = 30) -> Path:
    """Build forcing file for OpenDrift from oceanographic data"""
    # Constants from OpenDriftFinal notebook
    START_TIME0 = np.datetime64("2000-01-01T00:00:00")
    
    ref = rxr.open_rasterio(get_optical_ref(date_dir)).squeeze(drop=True)
    bio0, bio1 = date_dir/"bio_s2", sar_dir/"bio"

    # --- S2-time
    uo0, vo0 = _open_match(bio0/"uo.tif", ref), _open_match(bio0/"vo.tif", ref)
    vsdx0, vsdy0 = _open_match(bio0/"vsdx.tif", ref), _open_match(bio0/"vsdy.tif", ref)
    swh0 = _open_match(bio0/"swh.tif", ref) if (bio0/"swh.tif").exists() else xr.zeros_like(uo0)
    if (bio0/"u10.tif").exists() and (bio0/"v10.tif").exists():
        u10_0, v10_0 = _open_match(bio0/"u10.tif", ref), _open_match(bio0/"v10.tif", ref)
    else:
        wspd0, wdir0 = _open_match(bio0/"wind.tif", ref), _open_match(bio0/"wind_dir.tif", ref)
        th0 = np.deg2rad(wdir0)
        u10_0 = (wspd0*np.sin(th0)).astype("float32")
        v10_0 = (wspd0*np.cos(th0)).astype("float32")

    # --- SAR-time
    uo1, vo1 = _open_match(bio1/"uo.tif", ref), _open_match(bio1/"vo.tif", ref)
    vsdx1, vsdy1 = _open_match(bio1/"vsdx.tif", ref), _open_match(bio1/"vsdy.tif", ref)
    swh1 = _open_match(bio1/"swh.tif", ref) if (bio1/"swh.tif").exists() else xr.zeros_like(uo1)
    if (bio1/"u10.tif").exists() and (bio1/"v10.tif").exists():
        u10_1, v10_1 = _open_match(bio1/"u10.tif", ref), _open_match(bio1/"v10.tif", ref)
    else:
        wspd1, wdir1 = _open_match(bio1/"wind.tif", ref), _open_match(bio1/"wind_dir.tif", ref)
        th1 = np.deg2rad(wdir1)
        u10_1 = (wspd1*np.sin(th1)).astype("float32")
        v10_1 = (wspd1*np.cos(th1)).astype("float32")

    # decimate
    uo0,vo0,vsdx0,vsdy0,u10_0,v10_0,swh0 = map(lambda d:_dec(d, decimate), (uo0,vo0,vsdx0,vsdy0,u10_0,v10_0,swh0))
    uo1,vo1,vsdx1,vsdy1,u10_1,v10_1,swh1 = map(lambda d:_dec(d, decimate), (uo1,vo1,vsdx1,vsdy1,u10_1,v10_1,swh1))

    # lat/lon
    xs, ys = uo0.x.values, uo0.y.values
    X, Y = np.meshgrid(xs, ys)
    to_wgs = Transformer.from_crs(ref.rio.crs, 4326, always_xy=True)
    lon, lat = to_wgs.transform(X, Y)

    # time from Δt folder
    m = re.search(r"SAR_([+-]?\d+\.?\d*)h", sar_dir.name)
    if not m:
        raise ValueError(f"Bad SAR dir: {sar_dir}")
    delta_h = float(m.group(1))
    times = np.array([START_TIME0, START_TIME0 + np.timedelta64(int(abs(delta_h)*3600), 's')], dtype='datetime64[ns]')

    ds = xr.Dataset(
        coords=dict(
            time=("time", times),
            y=("y", np.arange(lon.shape[0], dtype=np.int32)),
            x=("x", np.arange(lon.shape[1], dtype=np.int32)),
            latitude =(("y","x"), lat.astype("float32")),
            longitude=(("y","x"), lon.astype("float32")),
        ),
        data_vars=dict(
            uo   =(("time","y","x"), np.stack([uo0.values,   uo1.values]).astype("float32")),
            vo   =(("time","y","x"), np.stack([vo0.values,   vo1.values]).astype("float32")),
            vsdx =(("time","y","x"), np.stack([vsdx0.values, vsdx1.values]).astype("float32")),
            vsdy =(("time","y","x"), np.stack([vsdy0.values, vsdy1.values]).astype("float32")),
            u10  =(("time","y","x"), np.stack([u10_0.values, u10_1.values]).astype("float32")),
            v10  =(("time","y","x"), np.stack([v10_0.values, v10_1.values]).astype("float32")),
            swh  =(("time","y","x"), np.stack([swh0.values,  swh1.values]).astype("float32")),
        )
    )
    # CF attrs
    ds["uo"].attrs.update(  standard_name="eastward_sea_water_velocity",  units="m s-1")
    ds["vo"].attrs.update(  standard_name="northward_sea_water_velocity", units="m s-1")
    ds["vsdx"].attrs.update(standard_name="sea_surface_wave_stokes_drift_x_velocity", units="m s-1")
    ds["vsdy"].attrs.update(standard_name="sea_surface_wave_stokes_drift_y_velocity", units="m s-1")
    ds["u10"].attrs.update( standard_name="eastward_wind",  units="m s-1")
    ds["v10"].attrs.update( standard_name="northward_wind", units="m s-1")
    ds["swh"].attrs.update( standard_name="sea_surface_wave_significant_height", units="m")

    out_nc = sar_dir/"forcing_plast.nc"
    _atomic_netcdf_write(ds, out_nc)
    print(f"Generated forcing file: {out_nc}")
    return out_nc

def create_24h_drift_animation(date_dir, shp_root, output_file="drift_24h_animation.gif"):
    """
    Create a 24+ hour drift animation focused on a ~20 km² area
    
    Parameters:
    -----------
    date_dir : Path
        Path to the date directory containing SAR and optical data
    output_file : str
        Output filename for the animation
    """
    
    # Find SAR directory (SAR_+Xh pattern)
    sar_dirs = [d for d in date_dir.iterdir() if d.is_dir() and re.match(r'SAR_[+-]?\d+\.?\d*h', d.name)]
    if not sar_dirs:
        raise ValueError(f"No SAR directory found in {date_dir}")
    sar_dir = sar_dirs[0]
    
    # Check for forcing file - generate if missing
    forcing_file = sar_dir / "forcing_plast.nc"
    if not forcing_file.exists():
        print(f"Forcing file not found, generating: {forcing_file}")
        forcing_file = build_plast_forcing(date_dir, sar_dir, decimate=30)
    
    print(f"Using data from: {date_dir.name}")
    print(f"SAR directory: {sar_dir.name}")
    print(f"Forcing file: {forcing_file}")
    
    # Get scene information and find matching shapefile
    try:
        ref_path, tile, date_iso = parse_scene_from_ref(date_dir)
        print(f"Scene: {tile} on {date_iso}")
        
        # Find matching shapefile
        shp_path = find_matching_shp(shp_root, tile, date_iso)
        if shp_path is None:
            raise ValueError(f"No matching shapefile found for {tile} on {date_iso}")
        
        print(f"Found matching shapefile: {shp_path.name}")
        
    except Exception as e:
        print(f"Error finding shapefile: {e}")
        raise
    
    # Extract seed coordinates from shapefile
    lons, lats = seeds_wgs84_from_shp(shp_path)
    if not lons:
        raise RuntimeError("No id==1 features found in shapefile")
    
    print(f"Found {len(lons)} seed locations from shapefile")
    
    # Initialize PlastDrift model
    o = PlastDrift(loglevel=20)
    o.set_config('general:use_auto_landmask', True)            # add GSHHG landmask
    o.set_config('drift:use_tabularised_stokes_drift', False)  # use VSDX/VSDY provided
    o.set_config('seed:wind_drift_factor', 0.03)               # 3% windage for macroplastics
    
    # Add reader for forcing data
    reader = reader_netCDF_CF_generic.Reader(str(forcing_file))
    o.add_reader(reader)
    
    # Set simulation parameters
    start_time = reader.start_time
    end_time = start_time + timedelta(hours=20)  # 30 hours for extended simulation
    
    # Create ensemble - multiple particles per detected location
    ensemble_n = 20  # particles per detected location
    lons_e = np.repeat(lons, ensemble_n)
    lats_e = np.repeat(lats, ensemble_n)
    
    print(f"Seeding {len(lons_e)} particles ({ensemble_n} per location)")
    print(f"Simulation from {start_time} to {end_time}")
    
    # Seed particles at detected debris locations
    seed_time = pd.Timestamp("2000-01-01T00:00:00").to_pydatetime()
    o.seed_elements(
        lon=lons_e.tolist(), 
        lat=lats_e.tolist(),
        number=len(lons_e), 
        time=seed_time,
        z=0.0, 
        terminal_velocity=0.01  # m/s buoyant rise
    )
    
    # Add windage variability per element
    n_el = o.elements.lon.size
    windage_std = 0.01  # ± spread per member
    if windage_std > 0 and n_el > 0:
        o.elements.wind_drift_factor = (
            o.elements.wind_drift_factor + np.random.normal(0, windage_std, size=n_el)
        )
    
    # Run simulation with appropriate time steps
    time_step = 1800  # 30 minutes
    time_step_output = 3600  # 1 hour output intervals
    
    print("Running OpenDrift simulation...")
    o.run(
        end_time=end_time, 
        time_step=time_step, 
        time_step_output=time_step_output
    )
    
    # Create focused visualization
    print("Creating plots...")
    
    # Calculate bounds for ~20 km² area around the drift
    # Get final positions to determine appropriate bounds
    try:
        final_lons = o.result['lon'].isel(time=-1).values
        final_lats = o.result['lat'].isel(time=-1).values
    except:
        # Fallback for older OpenDrift versions
        final_lons = o.get_property('lon')[-1]
        final_lats = o.get_property('lat')[-1]
    
    # Remove NaN values
    final_lons = np.asarray(final_lons).ravel()
    final_lats = np.asarray(final_lats).ravel()
    valid_mask = ~(np.isnan(final_lons) | np.isnan(final_lats))
    final_lons = final_lons[valid_mask]
    final_lats = final_lats[valid_mask]
    
    # Calculate bounds with some padding around initial and final positions
    all_lons = np.concatenate([lons, final_lons])
    all_lats = np.concatenate([lats, final_lats])
    
    lon_center = np.mean(all_lons)
    lat_center = np.mean(all_lats)
    
    # For ~20 km² area, use appropriate degrees based on actual spread
    lon_range = max(0.05, np.std(all_lons) * 2.5)  # minimum 0.05 degrees
    lat_range = max(0.04, np.std(all_lats) * 2.5)  # minimum 0.04 degrees
    
    bounds = [
        float(lon_center - lon_range),  # min_lon
        float(lon_center + lon_range),  # max_lon
        float(lat_center - lat_range),  # min_lat
        float(lat_center + lat_range)   # max_lat
    ]
    
    print(f"Plot bounds: {bounds}")
    
    # Create static plot with trajectories (more reliable than animation)
    try:
        o.plot(
            filename=output_file.replace('.gif', '_trajectories.png'),
            show_trajectories=True,
            trajectory_alpha=0.5,
            markersize=3,
            color='red',
            background='cartopy',
            corners=bounds  # Use corners instead of bounds
        )
        print(f"Trajectory plot saved as: {output_file.replace('.gif', '_trajectories.png')}")
    except Exception as e:
        print(f"Error creating trajectory plot: {e}")
        # Fallback to basic plot without bounds
        try:
            o.plot(
                filename=output_file.replace('.gif', '_basic.png'),
                show_trajectories=True,
                trajectory_alpha=0.5,
                markersize=3,
                color='red'
            )
            print(f"Basic plot saved as: {output_file.replace('.gif', '_basic.png')}")
        except Exception as e2:
            print(f"Error creating basic plot: {e2}")
    
    # Try creating animation with simpler parameters
    try:
        print("Attempting to create animation...")
        o.animation(
            filename=output_file,
            fast=False,  # Don't use fast mode
            show_elements=True,
            show_trajectories=False,  # Disable trajectories to avoid issues
            markersize=1,
            color='red'
        )
        print(f"Animation saved as: {output_file}")
    except Exception as e:
        print(f"Animation creation failed: {e}")
        print("Static plots were created instead.")
    
    print(f"Animation saved as: {output_file}")
    
    # Print summary statistics
    print("\nSimulation Summary:")
    print(f"Duration: {(end_time - start_time).total_seconds() / 3600:.1f} hours")
    print(f"Particles seeded: {len(lons_e)}")
    print(f"Particles seeded: {number_particles}")
    print(f"Final particle spread: {np.std(final_lons):.4f}° lon, {np.std(final_lats):.4f}° lat")
    
    return o

# Main execution
if __name__ == "__main__":
    try:
        # Set paths (from OpenDriftFinal notebook)
        shp_root = Path(r"D:\Masters\marine-debris.github.io\data\shapefiles")
        
        # Get the third date folder automatically
        third_date_dir = get_third_date_folder()
        print(f"Processing third date folder: {third_date_dir.name}")
        
        # Create the animation
        drift_model = create_24h_drift_animation(
            date_dir=third_date_dir,
            shp_root=shp_root,
            output_file=f"marine_debris_24h_{third_date_dir.name}.gif"
        )
        
        # Optional: Create additional plots
        print("\nCreating summary plot...")
        drift_model.plot(
            filename=f"drift_summary_24h3_{third_date_dir.name}.png",
            show_trajectories=True,
            trajectory_alpha=0.5,
            markersize=3,
            background='cartopy'
        )
        
        print("Analysis complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you're running this script from the drift directory containing the date folders.")
        print("Also ensure the shapefile directory path is correct.")
