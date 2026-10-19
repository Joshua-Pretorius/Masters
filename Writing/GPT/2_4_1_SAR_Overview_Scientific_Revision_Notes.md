# Scientific Revision Notes for Section 2.4.1

## Scope and outcome

This audit compares the two supplied versions of "2.4.1 Synthetic Aperture Radar Overview" and records the substantive changes made in the full literature-review draft. The source attachments were not edited.

The revised subsection is in:

`D:\Masters\Writing\Literature_Review_Sections_2_4_to_2_9_Draft.md`

The revision preserves the intended progression from basic SAR principles to polarisation, Sentinel-1 product choice, texture, and polarimetric features. It corrects claims that were scientifically inaccurate, too absolute, or not adequately supported, and it aligns the feature discussion with the actual master's processing chain.

## Scientific inaccuracies and overbroad claims

| Priority | Original claim or issue | Assessment | Correction applied |
|---|---|---|---|
| High | SAR can operate "in all weather conditions" regardless of cloud. | Cloud independence is a major SAR advantage, but "all weather" is too absolute. Heavy precipitation can affect microwave propagation, and weather changes the water surface being measured. | Described C-band SAR as day/night and largely cloud-insensitive or nearly all-weather, while identifying precipitation and weather-driven surface roughness as remaining influences. |
| High | Longer wavelengths have lower spatial resolution, while shorter wavelengths are more affected by cloud and capture finer features. | This incorrectly couples wavelength to spatial resolution. SAR resolution depends mainly on bandwidth, aperture, mode, and processing. Ordinary cloud is not the relevant short-versus-long microwave distinction. | Separated wavelength-dependent scattering and penetration from image resolution. Retained the valid point that wavelength changes the scale of interaction with the target. |
| Medium | A complete Ka-to-P band list is needed to explain sensor choice. | The ordering was broadly correct, but the list distracted from the project and supported an incorrect universal trade-off. | Focused the discussion on common spaceborne X-, C-, and L-band systems and then on Sentinel-1 C-band at approximately 5.405 GHz or 5.6 cm wavelength. |
| High | Single polarisation is especially suited to smooth surfaces with little vertical variability, such as water or soil. | This is too categorical. Channel suitability depends on geometry, roughness, dielectric properties, incidence angle, target contrast, and noise. | Removed the fixed surface-to-mode mapping and explained the information available in co- and cross-polarised channels without claiming universal superiority. |
| High | Dual polarisation "has been shown to be more effective" than single polarisation where small vertical changes separate targets. | Extra channels can improve discrimination, but performance is application-specific. Cross-pol can also be weak or noise-limited. | Reframed dual-pol as potentially complementary and explicitly made its benefit dependent on target response, incidence angle, sea state, and signal quality. |
| High | VH divided by VV is a "cross-correlation index." | This is incorrect. VH/VV is a polarisation intensity ratio. Cross-correlation requires complex measurements and is represented by the off-diagonal C2 term. | Defined the linear ratio and dB difference separately from complex covariance and normalised complex correlation. |
| High | Quad-pol decomposition separates the dominant scattering mechanism "per pixel." | This implies deterministic material identification from a speckled pixel. Polarimetric decompositions estimate components or eigenstructure under assumptions and generally require local statistical averaging. | Described full-pol decomposition as a model- or eigenanalysis-based representation whose interpretation depends on calibration, averaging, and model assumptions. |
| Medium | "Decomposition requires phase data to be preserved." | The central idea is correct but incomplete. Intensity-only polarimetric indices can be derived without relative phase, whereas complex covariance off-diagonal terms and coherent decompositions require complex calibrated channels. | Specified which dual-pol quantities require SLC phase and which can be formed from detected intensities. |
| High | GRD and SLC were called "unprocessed Sentinel-1" scenes. | Both are focused Level-1 products. SLC is not raw data, and GRD has additional detection, multilooking, and ground-range processing. | Replaced "unprocessed" with precise Level-1 product definitions. Any future figure captions should also avoid "unprocessed." |
| High | SLC retains full resolution because it is represented in slant-range coordinates. | Slant-range geometry does not cause high resolution. SLC retains the full available signal bandwidth and single-look sampling for the acquisition mode. | Corrected the causal explanation and avoided implying that SLC resolution is independent of acquisition mode. |
| Medium | Multilooking produces square pixels on a regular grid. | Multilooking averages looks and changes spatial and radiometric resolution. Approximately square ground-range sampling results from the broader detection, multilooking, projection, and resampling chain. | Described the operations separately and stated that multilooking reduces speckle variance rather than eliminating speckle. |
| Medium | GRD pixels contain only backscatter intensity. | Sentinel-1 GRD contains detected magnitude samples; calibrated intensity and backscatter coefficients are derived through radiometric calibration. The important contrast is the loss of complex phase. | Used "detected magnitude from which calibrated intensity or backscatter can be derived" and stated explicitly that complex phase is absent. |
| High | SLC generally detects finer targets than GRD. | SLC usually retains finer native sampling and more information, but detection also depends on signal-to-noise ratio, target contrast, processing, geometry, and the classifier. | Removed the universal performance claim and treated SLC as enabling additional candidate features whose value must be demonstrated. |
| High | SLC phase "allows for the derivation of polarimetric information and coherence." | This merges polarimetric cross-channel covariance with temporal interferometric coherence. Standard InSAR coherence requires at least two co-registered SLC acquisitions. | Distinguished simultaneous VV-VH covariance from temporal interferometric coherence and stated the data requirements for each. |
| High | Simpson et al. (2022) showed that "coherence" improves floating-object detection generally. | The study evaluated large plastic accumulations trapped near river dams using reference-image change detection and coherent polarimetric covariance information. Its main tested feature was not simply standard InSAR coherence, and the result is not automatically transferable to dispersed marine litter. | Reframed the evidence with its target scale, environment, detector type, and transfer limitations. |
| High | GLCM texture improves object-detection accuracy, cited to Li et al. (2022). | Texture may add useful context, but improvement is an empirical result, not a consequence of computing GLCM. The cited Li et al. paper in the library concerns UAV thermal-infrared oil-spill imagery rather than SAR plastic detection and does not directly support the claim. | Replaced the citation with the foundational GLCM source, explained why texture could be relevant, listed confounders, and required validation or ablation. |
| High | Dual-pol H-alpha parameters quantify the dominant scattering mechanism as though Sentinel-1 were fully polarimetric. | Sentinel-1 VV/VH lacks the second co-pol channel. Co-/cross-pol H-alpha descriptors have limited capacity to separate canonical surface, dipole/volume, and double-bounce mechanisms. | Defined the products as partial, basis-dependent dual-pol descriptors and explicitly prohibited one-to-one full-pol mechanism labels. |
| High | The pipeline output named "anisotropy" can be interpreted as classical Cloude-Pottier anisotropy. | The two-channel implementation uses an eigenvalue contrast based on lambda 1 and lambda 2. Classical full-pol anisotropy uses the second and third eigenvalues of a three-component matrix. | Defined the dual-pol quantity as \(A_2=(\lambda_1-\lambda_2)/(\lambda_1+\lambda_2)\), noted its relation to degree of polarisation, and distinguished it from full-pol anisotropy. |
| Medium | Polarimetric entropy, anisotropy, and alpha were presented as independent physical properties. | In a 2 x 2 decomposition, entropy and eigenvalue contrast are both functions of the same two normalised eigenvalues and may be strongly redundant. Alpha is also basis- and configuration-dependent. | Explained their mathematical relationship and treated them as candidate model inputs to be tested through ablation and feature-importance analysis. |

## Technical content added

The revised subsection now includes:

- A concise explanation of coherent SAR image formation and the synthetic aperture.
- A scientifically qualified explanation of day/night and cloud-independent operation.
- A separation between wavelength-dependent scattering and system-dependent spatial resolution.
- Definitions of co-pol, cross-pol, single-pol, dual-pol, and quad-pol measurements.
- A correct distinction between VH/VV intensity ratio, VV-VH covariance, normalised complex correlation, and interferometric coherence.
- Precise Sentinel-1 SLC and GRD Level-1 product definitions based on the ESA product specification.
- A bounded interpretation of the Simpson et al. (2022) river-plastic result.
- A GLCM explanation tied to the project's `vv_glcm_mean`, `vv_glcm_std`, and `vv_glcm_entropy` layers.
- The full dual-pol C2 matrix and the physical meaning of its diagonal and off-diagonal elements.
- Eigenvalue definitions for the project's dual-pol entropy, software-labelled anisotropy, and mean alpha products.
- A clear warning that Sentinel-1 VV/VH cannot support the same scattering-mechanism interpretation as full quad-pol data.
- A linking paragraph that moves from the feature definitions into Section 2.4.2 on ocean-surface physics.

## Alignment with the implemented pipeline

The writing was checked against the documented SLC processing chain. The implementation:

- retains calibrated VV and VH backscatter;
- computes VV GLCM mean, standard deviation, and entropy from a Refined Lee filtered branch;
- uses a 5 x 5 GLCM window, 32 grey levels, displacement 1, and all directions;
- builds the dual-pol C2 matrix from VV and VH complex data;
- applies SNAP's H-alpha dual-pol decomposition with a 5-pixel window; and
- exports `decomp_entropy`, `decomp_anisotropy`, and `decomp_alpha`.

The literature review explains the scientific purpose and limitations of these feature families. The numerical processing settings should remain in the methods chapter, where they can be reproduced and justified.

## Citation changes

Added or used directly in the revision:

- European Space Agency (2023), *Sentinel-1 Product Specification*, for SLC and GRD definitions.
- Haralick, Shanmugam, and Dinstein (1973), for the GLCM framework.
- Ji and Wu (2015), for the limitations of scattering-mechanism extraction from co-/cross-polarised dual-pol data.
- Mandal et al. (2020), for the dual-pol C2 and eigenvalue framework.
- Hajnsek and Desnos (2021), Simpson (2024), and Simpson et al. (2022), already present in the literature base.

Removed as support for this subsection:

- Johansson et al. (2017) for the wavelength-resolution-cloud claim, because the paper does not justify that universal relationship.
- Karjalainen et al. (2008) or a vegetation example as proof that dual-pol is universally superior.
- Li et al. (2022) as support for SAR GLCM plastic-detection performance.
- The incomplete Ferro-Famil and Pottier placeholder. A specific source should only be restored if a complete, directly relevant bibliographic record is selected.

## Remaining author decisions before thesis submission

1. If the GRD and SLC example figures are retained, describe them as Sentinel-1 Level-1 product examples and state the visualisation stretch and any preprocessing. Do not caption them as "unprocessed."
2. Confirm whether the thesis uses "grey" or "gray" consistently. The current prose uses British English "grey-level", while the standard feature name remains Grey-Level Co-occurrence Matrix.
3. Report the exact SNAP version and operator definitions in the methods chapter, particularly because the label "anisotropy" differs between dual- and full-polarimetric formulations.
4. State explicitly whether the VH/VV feature is computed in linear power or as a dB difference. These are related but should not be mixed.
5. Evaluate the covariance-derived features through ablation. If entropy and anisotropy are redundant in the empirical dataset, retain that result rather than forcing separate physical interpretations.
6. Keep the central inference conservative: SAR may detect a debris-associated surface expression or accumulation context, not plastic polymer chemistry directly.
