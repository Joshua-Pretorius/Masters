# Literature Review Writing Skeleton

> Planning document for restructuring and completing the literature review. It is not a replacement for the thesis text. Its purpose is to keep the chapter argumentative, connected to the master's project and free from repetition.

## 1. Chapter-Level Argument

The chapter should make one connected argument:

> Marine plastic is environmentally important but difficult to observe consistently; optical remote sensing demonstrates that floating debris can be mapped but is limited by acquisition conditions; SAR offers more regular observation but responds indirectly and ambiguously to debris; machine learning may combine multiple SAR and environmental features, yet progress is constrained by scarce and uncertain labels; the project therefore develops a South African, drift-aware SAR dataset and evaluates a self-supervised Attention U-Net using physically informed features and realistic negative examples.

Every section should advance one part of this argument. Material that does not support the problem, the sensing mechanism, the data problem or a project decision should be shortened or removed.

## 2. Recommended Chapter Structure and Current Progress

The current draft contains two sections numbered 2.4.2 and two sections numbered 2.7. Use the following final structure:

| Section | Purpose | Target length | Content present | Thesis-ready | Focused time remaining |
| --- | --- | ---: | ---: | ---: | ---: |
| 2.1 Chapter Overview | State the chapter's progression and exact research context | 150-250 words | 75% | 55% | 1-2 hours |
| 2.2 Marine Plastic Pollution | Establish the problem, transport and South African oceanographic relevance | 1,200-1,600 words | 70% | 50% | 4-6 hours |
| 2.3 Monitoring Marine Plastic | Compare in-situ, optical and complementary sensor roles | 1,000-1,300 words | 75% | 55% | 3-5 hours |
| 2.4 Synthetic Aperture Radar for Plastic Detection | Explain the SAR measurement, ocean physics, detectability limits and lookalikes | 2,000-2,500 words | 95% | 70% | 4-6 hours |
| 2.5 Machine Learning | Justify segmentation, data fusion, Attention U-Net, self-supervision and evaluation | 1,600-2,100 words | 90% | 65% | 4-7 hours |
| 2.6 Available Labelled Data | Compare available resources and prove the Sentinel-1 dataset gap | 800-1,100 words | 90% | 65% | 3-4 hours |
| 2.7 Label Creation and Spatiotemporal Alignment | Explain evidence levels, temporal mismatch, drift and uncertainty | 800-1,100 words | 90% | 65% | 3-5 hours |
| 2.8 Related Work | Synthesise optical, SAR and detection-plus-drift research streams | 900-1,200 words | 90% | 65% | 3-5 hours |
| 2.9 Research Gaps and Project Position | Map unresolved gaps to specific project responses and limits | 500-750 words | 90% | 65% | 2-3 hours |

The strengthened chapter will probably be approximately 9,000 to 11,900 words before final trimming. This is a guide rather than a quota; the quality of synthesis and avoidance of repetition are more important than exact section lengths.

The two percentages measure different things:

- **Content present** means that usable prose, notes or evidence already exists either in the original review or in the new sections 2.4-2.9 draft.
- **Thesis-ready** means that the material has been integrated into one document, checked against the papers, converted to the required citation style, edited for repetition and connected cleanly to the research questions.

## 3. Overall Completion and Time Needed

### Current estimate

- **Approximately 85% of the necessary content now exists.**
- **Approximately 60-65% of the chapter is thesis-ready.**
- **Estimated focused work remaining for a strong supervisor-ready version: 33-52 hours.**
- At roughly 6 focused hours per day, this is about **6-9 working days**.
- At roughly 2-3 hours per day, this is about **2-3 weeks**.

These estimates assume that the existing 2.1-2.3 material and the new 2.4-2.9 draft are merged rather than rewritten from the beginning. They include the high-priority missing topics identified below, citation verification and one full chapter-level edit. They do not include time waiting for supervisor feedback or implementing a major change in research direction.

### Where the remaining time will go

| Remaining task | Estimated time | Result |
| --- | ---: | --- |
| Add the high-priority missing topics | 8-12 hours | Stronger local, sensor, fusion and evaluation argument |
| Merge the new 2.4-2.9 draft into the main review | 4-6 hours | One continuous, correctly numbered chapter |
| Strengthen and rebalance 2.1-2.3 | 4-6 hours | Better lead-in to SAR and less repetition |
| Verify claims and convert citations to live Zotero fields | 5-8 hours | Traceable, consistently styled evidence |
| Remove overlap and improve transitions across the whole chapter | 4-6 hours | A single argument rather than separate mini-essays |
| Final language, tables, terminology and formatting check | 4-6 hours | Supervisor-ready presentation |
| Contingency for unavailable sources or weak local evidence | 4-8 hours | Space for targeted reading without derailing the schedule |

### Completion scale used in this document

| Percentage | Meaning |
| ---: | --- |
| 0-20% | Section is absent or exists only as a heading |
| 25-40% | Notes or a few sources exist, but the argument is not drafted |
| 45-60% | A partial draft exists, with important evidence or synthesis missing |
| 65-80% | A complete draft exists but still needs integration, citation and editing |
| 85-95% | The argument is substantially complete and needs targeted refinement |
| 100% | Integrated, source-verified, consistently cited and ready for supervisor review |

The percentage should only be moved to 100% after the prose is inside the main thesis document and has passed the final checklist. A standalone draft is not automatically a finished thesis section.

## 4. Narrative Spine and Transitions

| From | Reason for moving forward | Transition the section should make |
| --- | --- | --- |
| 2.2 Problem | Plastic moves, aggregates and causes harm, so it must be monitored spatially and repeatedly | The scale and mobility of marine plastic require observations beyond isolated shoreline or vessel surveys. |
| 2.3 Monitoring | Optical methods are informative but restricted by cloud, daylight and timing | These limitations motivate an all-weather, day-night sensor, leading to SAR. |
| 2.4 SAR | SAR is available more consistently, but its signal is indirect and confused by the ocean background | Multiple ambiguous features require a context-sensitive model rather than a fixed threshold. |
| 2.5 Machine learning | A segmentation model can combine features, but it needs representative labels | Model choice cannot compensate for absent, imbalanced or uncertain training data. |
| 2.6 Data | Existing datasets are mainly optical, controlled or too small for the intended SAR task | The project must create labels rather than simply adopt an existing benchmark. |
| 2.7 Labels | Cross-sensor labels move between observation times and have unequal confidence | Related studies must be assessed by how they handle sensor evidence, alignment and uncertainty together. |
| 2.8 Related work | Existing studies contribute parts of a solution but not the complete local framework | Their combined limitations define the specific research gaps. |
| 2.9 Gaps | Each gap leads directly to a methodological decision | End with the project's contribution, not another general summary of plastic pollution. |

## 5. Section-by-Section Writing Plan

### 2.1 Chapter Overview

**Question answered:** What argument will this chapter establish?

Write one concise paragraph that previews the progression:

1. Define the scale and South African relevance of marine plastic.
2. Review monitoring methods and the strengths and limits of optical remote sensing.
3. Introduce SAR as a complementary sensor and explain its physical ambiguity.
4. Review segmentation models, labelled data and label-creation strategies.
5. Synthesize the gaps addressed by the project.

Do not report methods, channel counts or expected model performance here. End with a roadmap sentence that uses the final section numbering.

### 2.2 Marine Plastic Pollution

**Question answered:** Why is the target important, mobile and difficult to define?

#### 2.2.1 Classification and terminology

- Define marine litter, plastic litter, macroplastic, mesoplastic and microplastic using one consistent size convention.
- Distinguish floating plastic from beach litter, submerged debris and suspended microplastic.
- State that the remote-sensing target is an accumulation or surface expression, not all plastic in the water column.
- Explain why material size, buoyancy, shape, biofouling and aggregation affect visibility and transport.

#### 2.2.2 Sources, pathways and aggregation

- Separate land-based and sea-based inputs.
- Explain transport from rivers, stormwater, wastewater, shipping and fishing.
- Introduce fronts, convergence, windrows and retention zones as processes that convert dispersed pieces into potentially observable accumulations.
- Keep the physical transport explanation at concept level; reserve detailed drift modelling for 2.7.

#### 2.2.3 Environmental and socioeconomic effects

- Summarise ingestion, entanglement, habitat effects, contaminant transport and ecosystem-service impacts.
- Avoid a long catalogue. Use effects to establish significance, not to become a separate ecological review.

#### 2.2.4 South African context

- Explain why the South African coastline and Exclusive Economic Zone are relevant.
- Connect urban and river inputs and major ports to Durban, Gqeberha and Cape Town.
- Use region-specific evidence where available.
- End by stating that mobile and episodic accumulations require repeatable spatial monitoring.

#### 2.2.5 South African oceanography and likely accumulation settings

**Status: missing or underdeveloped - high priority.**

- Explain the contrasting Agulhas and Benguela systems at the level needed to understand transport and regional variability.
- Relate boundary currents, coastal counter-currents, upwelling, fronts, river plumes and port or bay retention to possible debris concentration.
- Explain why the three study regions are not interchangeable environmental domains.
- Distinguish evidence that a process transports or concentrates debris from evidence that plastic was actually observed.
- End by linking regional oceanography to the need for location-disjoint model evaluation.

**Avoid repeating:** generic pollution statistics in later remote-sensing sections.

**Link to 2.3:** The environmental problem is large and mobile, but the quantity of interest cannot be monitored adequately through sparse local observations alone.

### 2.3 Monitoring Marine Plastic

**Question answered:** What can existing monitoring methods observe, and why is there still an acquisition gap?

#### 2.3.1 In-situ monitoring

- Cover beach surveys, vessel observations, net sampling, drifters and UAV surveys.
- Compare directness, spatial coverage, temporal frequency and cost.
- Explain that direct observations are valuable as validation but cannot continuously cover the EEZ.

#### 2.3.2 Remote sensing

- Move from UAV and airborne sensing to satellite optical sensing.
- Explain the spectral logic of optical plastic detection and the importance of target concentration, pixel mixing, atmospheric effects and spatial resolution.
- Introduce PLP, FloatingObjects, MARIDA and high-resolution PlanetScope work as evidence that surface accumulations can be detected.
- State the limits: cloud, daylight, sunglint, water colour, mixed pixels and acquisition timing.
- Conclude that optical imagery is an important source of labels and confirmation, but not a complete operational observation stream.

#### 2.3.3 Complementary sensor roles, observation scale and timing

**Status: missing - high priority.**

- Compare what UAV, high-resolution optical, Sentinel-2 and Sentinel-1 observations measure rather than ranking them as universally better or worse.
- Explain spatial-resolution and revisit-time trade-offs, including sub-pixel targets and the need for dense accumulation before a satellite response becomes visible.
- Define the intended observation chain: direct or optical evidence supports confirmation and labelling, while Sentinel-1 provides the principal all-weather observation stream.
- Explain that cross-sensor complementarity creates a temporal-alignment problem, which is addressed later through drift-aware label construction.
- Avoid implying that an optical signature and a radar signature should occupy identical pixels without uncertainty.

**Avoid repeating:** full dataset specifications, which belong in 2.6.

**Link to 2.4:** A complementary sensor must increase temporal availability, but it will observe different physical properties from optical imagery.

### 2.4 Synthetic Aperture Radar for Plastic Detection

**Question answered:** What does SAR measure, how might plastic affect it, and why is interpretation uncertain?

#### 2.4.1 SAR overview

- Define active microwave imaging, amplitude, phase and synthetic aperture.
- Explain wavelength, incidence angle and polarisation without equating wavelength to spatial resolution.
- Introduce Sentinel-1 C-band VV/VH because it is the project's principal sensor.
- Explain GRD versus SLC precisely.
- State what SLC makes possible: coherent processing and dual-polarisation covariance information.
- Introduce the feature families used by the project only as a response to the literature:
  - VV and VH backscatter;
  - inter-polarisation ratio or difference;
  - local texture;
  - partial dual-polarisation descriptors.
- Do not turn this section into the Methods chapter by listing every preprocessing parameter.

#### 2.4.2 Ocean surface physics

- Start with smooth water as a dark specular reflector.
- Explain wind-generated roughness and resonant surface scattering.
- Add breaking waves and depolarisation.
- Explain roughness damping by oil or biogenic surfactants.
- Introduce fronts, plumes, internal waves, convergence and windrows.
- Explain why wind, wave, current and temperature data are contextual rather than target labels.

The ordering matters: readers must understand normal water before plastic-related anomalies.

#### 2.4.3 Floating plastic and SAR returns

Organise the evidence by mechanism, not publication date:

1. **Bright direct or roughness-related responses**
   - Simpson et al. for large river accumulations in Sentinel-1.
   - de Fockert et al. for controlled concentration and wave effects.
   - Nunziata et al. for controlled X-band target-water contrast.
2. **Variable observations**
   - Qi et al. for bright and dark marine-debris appearances and more stable bright macroalgae.
3. **Dark indirect proxies**
   - Davaasuren et al. and Evans and Ruf for surfactant-related roughness suppression.

Then state the synthesis explicitly: SAR does not directly identify polymer chemistry, and no universal plastic threshold is supported.

#### 2.4.4 Lookalikes and false detections

Group confusers by radar appearance:

- Dark: low wind, oil or biogenic films, sheltered water and current shadows.
- Bright: ships, wakes, whitecaps, rain cells, natural debris, macroalgae and infrastructure.
- Linear or structured: fronts, windrows, internal waves, river plumes and wakes.

Explain why a binary plastic-versus-random-water dataset is inadequate. Conclude with the need for hard-negative classes and environmental context.

#### 2.4.5 Detectability limits and Sentinel-1 acquisition constraints

**Status: partly present but not yet a distinct synthesis - high priority.**

- Explain why controlled X- and Ku-band thresholds cannot be transferred directly to Sentinel-1 C-band.
- Discuss target concentration, target-to-clutter ratio, sub-pixel mixing, sea state, incidence angle, polarisation and spatial resolution as detectability controls.
- Briefly identify SAR artefacts that can affect coastal analysis: speckle, thermal and border noise, calibration differences, mixed land-water pixels, geometric distortion and resampling.
- Separate scientifically meaningful preprocessing choices from implementation details that belong in Methods.
- State the practical consequence: detectability is conditional, so results must be stratified by acquisition and environmental conditions.

**Avoid repeating:** model architecture details.

**Link to 2.5:** The signal is multi-feature and context dependent, so the model must learn spatial combinations rather than a universal threshold.

### 2.5 Machine Learning

**Question answered:** Which model and training strategy best fit a rare, uncertain segmentation target?

Open by distinguishing classification from segmentation. The project needs target location and shape, so semantic segmentation is the primary task.

#### 2.5.1 Architectures

- Begin with shallow classifiers and the Savastano SAR pilot.
- Explain CNNs and residual encoders briefly.
- Explain U-Net's encoder, decoder and skip connections.
- Use optical marine-debris studies to show why spatial features and dense outputs are useful.
- Explain Attention U-Net as the primary architecture:
  - gates skip-connection information;
  - suppresses irrelevant background;
  - retains multi-scale spatial detail;
  - suits small targets in large backgrounds.
- Discuss transformers as an alternative with long-range context but higher data and compute demands.
- End with a reasoned choice, not a claim that Attention U-Net is universally superior.

#### 2.5.2 Training strategies

Use four subthemes:

1. **Physically valid augmentation**
   - flips, rotations, crops and controlled perturbations;
   - preserve relationships across SAR channels;
   - avoid arbitrary photographic colour augmentation.
2. **Self-supervised learning and embeddings**
   - use unlabelled local Sentinel-1 imagery;
   - explain an embedding as a compact learned representation;
   - pretrain the encoder and fine-tune it for segmentation;
   - use Pei et al. and Glaser et al. as evidence from adjacent SAR tasks.
3. **Class imbalance**
   - target-centred sampling;
   - representative background and hard negatives;
   - weighted BCE or focal loss with Dice/IoU loss;
   - precision-recall reporting and validation-set thresholding.
4. **Leakage and generalisation**
   - split by scene, event and location;
   - never randomly divide overlapping patches;
   - evaluate Durban, Gqeberha and Cape Town separately and across locations.

Add confidence-aware training at the end to create the link to labels.

#### 2.5.3 Environmental and multimodal data fusion

**Status: missing - high priority.**

- Explain the difference between adding environmental variables as model inputs and using them only for stratified analysis or interpretation.
- Compare early fusion, in which aligned channels are stacked, with later fusion, in which separate encoders or decision stages combine information.
- Discuss the different spatial and temporal resolutions of SAR, wind, waves, currents and sea-surface temperature.
- Warn against information leakage where a variable used to create a label is also presented to the model as apparently independent evidence.
- Justify an ablation study that compares SAR-only, SAR-feature and SAR-plus-environment configurations.

#### 2.5.4 Generalisation, probability calibration and evaluation

**Status: partly present but needs a dedicated synthesis - high priority.**

- Explain geographic and environmental domain shift between Durban, Gqeberha and Cape Town.
- Distinguish patch-level, scene-level, event-level and location-level generalisation.
- Explain why overall accuracy and ROC-AUC can be misleading for a rare segmentation target.
- Justify precision, recall, F1 score, intersection over union, precision-recall curves and false alarms per scene or area.
- Include probability calibration or reliability analysis so that predicted confidence can be compared with label confidence.
- Require ablation and sensitivity tests for feature groups, self-supervised pretraining, drift adjustment and uncertain-label handling.
- State that a held-out location or acquisition provides stronger evidence than a random patch split.

**Avoid repeating:** detailed model hyperparameters and training schedule.

**Link to 2.6:** The defensibility of this training strategy depends on the type, scale and reliability of available labels.

### 2.6 Available Labelled Data

**Question answered:** What labelled evidence exists, and why can it not simply be reused as the final training set?

Keep one comparison table with these columns:

- source;
- sensor and setting;
- label type;
- relevance;
- limitation.

Include at least:

- PLP2018/2019;
- FloatingObjects;
- MARIDA;
- PlanetScope/NASA Marine Debris data used in later data-centric studies;
- Savastano's Sentinel-1/Sentinel-2 pilot;
- Simpson's Sentinel-1 river accumulations;
- de Fockert's controlled radar experiment;
- Nunziata's controlled X-band campaign;
- CYGNSS roughness-based proxy.

After the table, synthesise rather than repeat each row:

- optical labels are larger and more mature;
- controlled radar evidence supports physical feasibility;
- direct Sentinel-1 data are small or domain-specific;
- proxy products are not confirmed object labels;
- no existing resource matches the local, multi-scene SLC segmentation task.

**Avoid repeating:** all model results from the related-work section.

**Link to 2.7:** Because a suitable benchmark does not exist, label construction and its uncertainty become part of the research problem.

### 2.7 Label Creation and Spatiotemporal Alignment

**Question answered:** How can observations from different sensors and times become defensible SAR labels?

Build the section in this order:

1. State the temporal-alignment problem.
2. Explain the main transport mechanisms:
   - surface currents;
   - windage;
   - Stokes drift;
   - tides, fronts and turbulence;
   - object-specific behaviour.
3. Explain what OpenDrift contributes.
4. Explain why a single trajectory is not ground truth.
5. Define an ensemble probability surface or search envelope.
6. Define the four-level evidence hierarchy.
7. State the provenance fields stored with each label.
8. Explain validation and no-drift versus drift sensitivity testing.

Use the following evidence hierarchy consistently throughout the thesis:

| Level | Evidence | Appropriate use |
| --- | --- | --- |
| A | Synchronous direct confirmation | High-confidence supervised label and evaluation |
| B | Near-coincident optical or other transfer | Supervised label with measured alignment tolerance |
| C | Ensemble drift-adjusted estimate | Soft or confidence-weighted label |
| D | Front, anomaly or broad proxy | Candidate discovery, manual review or self-supervision; not a confirmed positive |

**Avoid repeating:** full equations or OpenDrift configuration, which belong in Methods.

**Link to 2.8:** This hierarchy provides the standard by which related detection and transport studies can be compared.

### 2.8 Related Work

**Question answered:** Which parts of the intended framework have been demonstrated, and which combination is missing?

Write this as a synthesis, not a second list of papers.

#### Stream 1: Optical datasets and segmentation

- PLP -> controlled evidence.
- FloatingObjects and MARIDA -> benchmark construction and spatial segmentation.
- Rußwurm et al. -> data harmonisation, hard negatives and label quality.
- Booth et al. -> spatial prediction in high-resolution imagery.

End the stream by saying these studies provide annotation and modelling lessons, but not radar feature relationships.

#### Stream 2: Radar detection

- Davaasuren and CYGNSS -> indirect dark roughness proxies.
- Savastano -> early Sentinel-1 shallow classification with optical transfer.
- Simpson -> direct large-accumulation Sentinel-1 evidence and SLC value.
- Qi -> variable marine-debris signature and macroalgae confusion.
- de Fockert and Nunziata -> controlled physics and natural-material confusion.

End the stream by stating that the evidence supports feasibility but not a universal signature or open deep-segmentation benchmark.

#### Stream 3: Detection plus transport

- van Sebille et al. -> physical transport foundation.
- OpenDrift studies -> implementation and uncertainty.
- DEEP-PLAST -> integrated detection and drift concept.

End by saying transport can align evidence but cannot create certainty from an unconfirmed source observation.

#### Final synthesis

State what the literature has not yet combined:

- local South African Sentinel-1 SLC;
- multiple physically motivated SAR features;
- environmental context;
- drift-aware probabilistic labels;
- self-supervised local pretraining;
- Attention U-Net segmentation;
- scene- and location-disjoint evaluation.

**Avoid repeating:** the full gap list. Reserve the direct project response for 2.9.

### 2.9 Research Gaps and Project Position

**Question answered:** What exactly is unresolved, and how does the project respond?

Use five paired gap-response paragraphs:

| Gap in literature | Project response |
| --- | --- |
| Variable bright and dark SAR responses | Learn across VV, VH, inter-polarisation, texture and dual-polarisation descriptors rather than impose one threshold |
| Strong natural and anthropogenic lookalikes | Include explicit hard negatives and wind, wave, current and temperature context |
| No suitable South African Sentinel-1 segmentation dataset | Build a provenance-rich dataset around Durban, Gqeberha and Cape Town |
| Temporal mismatch and uncertain transferred labels | Use ensemble drift adjustment, soft labels and confidence levels |
| Too few labels for robust supervised learning | Pretrain on unlabelled local SAR, then fine-tune an Attention U-Net |

End with a bounded contribution statement:

> The study evaluates whether candidate floating-plastic accumulations can be segmented from realistic South African coastal SAR backgrounds under explicit uncertainty. It does not assume that SAR uniquely identifies polymer composition or claim to deliver an operational monitoring system.

## 6. Missing or Underdeveloped Topics by Priority

The following additions would strengthen the review most. The high-priority items are already reflected in the recommended subsection structure above and are included in the 33-52 hour completion estimate.

| Priority | Missing or weak topic | Best placement | What it adds to the argument | Estimated effort |
| --- | --- | --- | --- | ---: |
| High | South African oceanography and accumulation settings | New 2.2.5 | Explains why Durban, Gqeberha and Cape Town represent different transport and observation domains | 2-3 hours |
| High | Complementary sensor roles, scale and timing | New 2.3.3 | Clarifies why optical evidence supports labels while SAR remains the principal observation source | 1.5-2.5 hours |
| High | Detectability limits and Sentinel-1 constraints | New 2.4.5 | Prevents controlled radar results from being overgeneralised to C-band coastal imagery | 2-3 hours |
| High | Environmental and multimodal data fusion | New 2.5.3 | Provides a literature-based justification for adding wind, waves, currents or temperature and for testing whether they help | 2-3 hours |
| High | Domain shift, calibration and rare-target evaluation | New 2.5.4 | Connects the three-location design to defensible validation and uncertainty reporting | 2.5-4 hours |
| Medium | Annotation consistency and reviewer agreement | Closing part of 2.6 and 2.7 | Adds guidance on polygon rules, ambiguous boundaries, repeated review and agreement between annotators | 1.5-2.5 hours |
| Medium | Dataset harmonisation and provenance standards | Closing part of 2.6 | Explains how labels from optical, UAV, field and drift-derived sources can coexist without being treated as equivalent | 1-2 hours |
| Medium | Reproducibility and open benchmark practice | Closing part of 2.8 or 2.9 | Supports the contribution of versioned data, scene-disjoint splits, documented preprocessing and reusable evaluation | 1-2 hours |
| Medium | Operational and scientific limits | Final paragraph of 2.9 | Defines the detectable target scale, expected false alarms, geographic scope and distinction between research framework and operational monitoring | 1-1.5 hours |
| Optional | Policy and governance response to marine litter | Short paragraph in 2.2 only if required | Connects detection to management relevance, but does not directly justify the sensing method | 1-2 hours |
| Optional | Broader microplastic chemistry and toxicity | Do not add unless the research question changes | Adds ecological context but risks distracting from floating surface accumulations detectable at satellite scale | 2-4 hours |

### Recommended additions to 2.6 and 2.7

The annotation topics do not require new top-level numbered sections, but they should be visible:

- Define a common annotation protocol for target boundary, minimum size and ambiguous pixels.
- Record whether each label was drawn, transferred, modelled or manually corrected.
- Use a second review pass or a subset reviewed by another annotator.
- Report agreement or disagreement rather than silently resolving every difference.
- Version the labels so that later drift or evidence corrections are traceable.
- Prevent the same physical event from appearing in both training and test data through different sensors or dates.

### Topics that should not become large standalone sections

These subjects may be mentioned, but expanding them would weaken the chapter's focus:

- detailed plastic policy, legislation and waste-management interventions;
- polymer chemistry unrelated to a radar- or optical-scale surface response;
- full SAR preprocessing equations and software parameters;
- full OpenDrift configuration and trajectory equations;
- model implementation details, hyperparameter searches and computing infrastructure;
- a general history of deep learning unrelated to segmentation, scarce labels or remote sensing.

## 7. Evidence-to-Decision Matrix

Use this matrix to keep the literature linked to the project rather than merely descriptive.

| Literature conclusion | Consequence for the master's project |
| --- | --- |
| Cloud and daylight limit optical availability | Use Sentinel-1 as the principal observation source and optical imagery as supporting evidence |
| SAR response depends on roughness, geometry and sea state | Use multiple SAR features and record acquisition/environmental conditions |
| Plastic may appear bright or dark | Avoid a universal intensity threshold |
| Natural material, ships, slicks and fronts create similar signatures | Design hard-negative classes and scene-level review |
| SLC can preserve useful coherent and polarimetric information | Retain and process SLC rather than restricting the study to GRD intensity |
| Labelled SAR plastic data are scarce | Build a new local dataset with complete provenance |
| Unlabelled SAR data are abundant | Use self-supervised representation learning |
| Optical and SAR observations may be separated in time | Model drift and preserve uncertainty |
| Random patches leak scene information | Split by acquisition, event and location |
| Rare-target accuracy can be misleading | Report precision, recall, F1, IoU and precision-recall behaviour |

## 8. Linking-Statement Templates

Adapt these statements to the surrounding prose rather than copying all of them verbatim.

- **Problem to monitoring:** "The mobility and spatial extent of floating debris make repeatable synoptic observation necessary, but they also limit the representativeness of local surveys."
- **Optical to SAR:** "Optical imagery supplies the clearest existing satellite evidence of floating debris, yet cloud, daylight and acquisition timing motivate a complementary active sensor."
- **SAR physics to plastic:** "Because SAR records the state of the water surface rather than polymer chemistry, any plastic-related anomaly must be interpreted through the scattering processes that create it."
- **Plastic response to lookalikes:** "The same mechanisms that make an accumulation visible also permit natural and anthropogenic features to produce similar contrast."
- **Lookalikes to machine learning:** "This ambiguity shifts the task from single-feature thresholding to contextual segmentation across multiple evidence channels."
- **Machine learning to data:** "The capacity of the model is secondary to whether its labels and negative examples represent the intended coastal environment."
- **Data to labels:** "The absence of a suitable Sentinel-1 benchmark makes label construction, alignment and provenance part of the scientific contribution."
- **Labels to related work:** "A comparison of existing studies must therefore consider not only reported model performance but also what was observed, how labels were aligned and how uncertainty was represented."
- **Related work to gaps:** "Existing work demonstrates each component separately, but does not yet integrate them into a local, uncertainty-aware Sentinel-1 segmentation framework."

## 9. Citation and Claim Discipline

- Distinguish **direct detection**, **surface-response detection** and **proxy inference**.
- Do not describe CYGNSS or dark-slick studies as direct confirmation of plastic.
- Do not generalise controlled X- or Ku-band thresholds to Sentinel-1 C-band.
- Do not generalise river-barrier performance to open coastal water.
- Use review papers to frame a field, but cite the original experiment for a numerical result.
- Put a citation next to the specific claim it supports.
- Use numerical dataset counts only where they clarify scarcity, scale or imbalance.
- Check every author-date citation against Zotero before submission.
- Replace the draft's plain citations with live Zotero fields only after the structure is accepted.
- Keep Methods details out of the literature review unless they are needed to explain why a project decision follows from prior work.

## 10. Recommended Writing Order

The easiest order is not the final reading order:

1. Add 2.2.5 and 2.3.3 so that the local and cross-sensor problem is established before SAR.
2. Add 2.4.5 to bound what Sentinel-1 can plausibly detect.
3. Add 2.5.3 and 2.5.4 so that environmental fusion and evaluation are justified.
4. Finalise 2.6 and 2.7, including annotation consistency and provenance.
5. Merge the completed 2.4-2.9 prose into the main review and remove duplicate material.
6. Rewrite 2.8 as a synthesis of optical, radar and transport work.
7. Rewrite 2.9 by pairing each demonstrated gap with one project response and one scope limit.
8. Revisit 2.2 and 2.3 to remove material repeated later.
9. Convert all citations to live Zotero fields and verify each claim against the source.
10. Write 2.1 last so that its roadmap matches the finished chapter.
11. Run one chapter-wide edit for transitions, terminology, word count and formatting.

After each numbered section is integrated and source-checked, update both progress percentages in Section 2. Do not increase the thesis-ready percentage merely because more raw prose has been added.

## 11. Final Revision Checklist

- [ ] Section numbering runs from 2.1 to 2.9 with no duplicates.
- [ ] The introduction previews the same structure the chapter actually follows.
- [ ] Every section begins with a question or claim, not a paper summary.
- [ ] Every section ends by creating a reason for the next section.
- [ ] SAR wavelength is not incorrectly equated with spatial resolution.
- [ ] GRD and SLC are described accurately.
- [ ] Dual-polarisation descriptors are not presented as full quad-polarimetric decomposition.
- [ ] Bright direct returns and dark indirect proxies are clearly separated.
- [ ] Lookalikes are treated as a core modelling problem.
- [ ] South African oceanography explains why the three study locations are distinct.
- [ ] Sensor scale, revisit timing and cross-sensor alignment are compared explicitly.
- [ ] Controlled-frequency results are not transferred directly to Sentinel-1 C-band.
- [ ] Sentinel-1 acquisition and coastal-processing artefacts are acknowledged.
- [ ] Environmental data fusion is justified and tested without label leakage.
- [ ] Domain shift, probability calibration and rare-target evaluation are addressed.
- [ ] Optical datasets are not presented as ready-made SAR labels.
- [ ] Temporal alignment and label confidence are explicit.
- [ ] Annotation rules, provenance and versioning are documented.
- [ ] Self-supervised embeddings are explained in plain language.
- [ ] Data splits are by scene, event or location rather than overlapping patch.
- [ ] The South African context reappears in the gap and contribution sections.
- [ ] The final contribution is bounded as a research framework, not an operational detection claim.
- [ ] All plain author-date citations have been verified and converted to the required thesis style.
