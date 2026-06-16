import cdsapi

c = cdsapi.Client()

c.retrieve(
    'reanalysis-era5-single-levels',
    {
        'product_type': 'reanalysis',
        'variable': [
            '10m_u_component_of_wind', '10m_v_component_of_wind',
        ],
        'year': '2023',
        'month': '05',
        'day': '12',
        'time': [
            '00:00', '06:00', '12:00', '18:00',
        ],
        'area': [ -30, 15, -35, 20 ],  # North, West, South, East
        'format': 'netcdf',
    },
    'test_download.nc')
