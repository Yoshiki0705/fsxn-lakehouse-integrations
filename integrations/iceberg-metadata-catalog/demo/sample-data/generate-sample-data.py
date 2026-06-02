#!/usr/bin/env python3
"""
generate-sample-data.py — Generate Realistic Sample Metadata for Demos

Creates realistic unstructured file metadata for demonstration purposes.
Supports multiple industry verticals with appropriate file names, types,
and sizes.

Usage:
    python generate-sample-data.py --industry manufacturing --count 100
    python generate-sample-data.py --industry financial --count 50 --output ./data
    python generate-sample-data.py --industry healthcare --count 200 --upload
"""

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path


# Industry-specific file templates
INDUSTRY_DATA = {
    "manufacturing": {
        "departments": ["engineering", "quality", "production", "maintenance", "safety"],
        "file_templates": [
            {"pattern": "P-{part_num}_{component}_v{ver}.step", "type": ".step", "size_range": (5_000_000, 50_000_000), "classification": "engineering"},
            {"pattern": "{component}_assembly_drawing.dwg", "type": ".dwg", "size_range": (2_000_000, 30_000_000), "classification": "engineering"},
            {"pattern": "QC_report_{date}_{line}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "quality"},
            {"pattern": "maintenance_log_{equipment}_{date}.xlsx", "type": ".xlsx", "size_range": (100_000, 2_000_000), "classification": "maintenance"},
            {"pattern": "safety_inspection_{area}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 8_000_000), "classification": "safety"},
            {"pattern": "BOM_{product}_rev{ver}.xlsx", "type": ".xlsx", "size_range": (200_000, 5_000_000), "classification": "engineering"},
            {"pattern": "production_schedule_{month}.xlsx", "type": ".xlsx", "size_range": (100_000, 1_000_000), "classification": "production"},
            {"pattern": "{product}_test_results_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 15_000_000), "classification": "quality"},
            {"pattern": "training_video_safety_{topic}.mp4", "type": ".mp4", "size_range": (50_000_000, 500_000_000), "classification": "training"},
            {"pattern": "ISO9001_procedure_{proc_id}.pdf", "type": ".pdf", "size_range": (500_000, 3_000_000), "classification": "compliance"},
        ],
        "components": ["pump_housing", "valve_body", "shaft_coupling", "bearing_mount", "gear_box", "motor_bracket", "heat_exchanger", "pressure_vessel", "turbine_blade", "impeller"],
        "products": ["HX-2000", "VP-500", "CP-1200", "TG-800", "PM-3000"],
        "equipment": ["CNC-01", "Press-A3", "Lathe-07", "Robot-12", "Furnace-02"],
        "areas": ["Zone-A", "Zone-B", "Assembly-1", "Warehouse", "Loading-Dock"],
    },
    "financial": {
        "departments": ["accounting", "compliance", "legal", "risk", "treasury"],
        "file_templates": [
            {"pattern": "Q{quarter}_financial_report_{year}.xlsx", "type": ".xlsx", "size_range": (500_000, 10_000_000), "classification": "financial"},
            {"pattern": "{client}_contract_{year}.pdf", "type": ".pdf", "size_range": (1_000_000, 20_000_000), "classification": "legal"},
            {"pattern": "audit_report_{scope}_{year}.pdf", "type": ".pdf", "size_range": (2_000_000, 30_000_000), "classification": "compliance"},
            {"pattern": "risk_assessment_{portfolio}_{date}.xlsx", "type": ".xlsx", "size_range": (300_000, 5_000_000), "classification": "risk"},
            {"pattern": "board_minutes_{date}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "governance"},
            {"pattern": "NDA_{counterparty}_{year}.pdf", "type": ".pdf", "size_range": (500_000, 3_000_000), "classification": "legal"},
            {"pattern": "tax_filing_{jurisdiction}_{year}.pdf", "type": ".pdf", "size_range": (1_000_000, 15_000_000), "classification": "financial"},
            {"pattern": "KYC_documentation_{client}.pdf", "type": ".pdf", "size_range": (2_000_000, 10_000_000), "classification": "compliance"},
            {"pattern": "investment_memo_{deal}_{date}.docx", "type": ".docx", "size_range": (500_000, 5_000_000), "classification": "financial"},
            {"pattern": "regulatory_response_{regulator}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 8_000_000), "classification": "compliance"},
        ],
        "clients": ["Tanaka_Industries", "Suzuki_Holdings", "Yamamoto_Corp", "Global_Partners", "Pacific_Trading"],
        "portfolios": ["equity_JP", "fixed_income", "alternatives", "real_estate", "emerging_markets"],
        "regulators": ["FSA", "SEC", "FCA", "JFSA", "MAS"],
    },
    "healthcare": {
        "departments": ["radiology", "pathology", "research", "clinical_trials", "administration"],
        "file_templates": [
            {"pattern": "MRI_scan_{study_id}_{sequence}.dcm", "type": ".dcm", "size_range": (10_000_000, 500_000_000), "classification": "medical_imaging"},
            {"pattern": "CT_scan_{study_id}_{slice}.dcm", "type": ".dcm", "size_range": (5_000_000, 200_000_000), "classification": "medical_imaging"},
            {"pattern": "pathology_slide_{case_id}.svs", "type": ".svs", "size_range": (100_000_000, 2_000_000_000), "classification": "pathology"},
            {"pattern": "clinical_trial_{trial_id}_protocol.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "research"},
            {"pattern": "patient_consent_{trial_id}_{site}.pdf", "type": ".pdf", "size_range": (500_000, 3_000_000), "classification": "compliance"},
            {"pattern": "research_paper_draft_{topic}_{ver}.docx", "type": ".docx", "size_range": (1_000_000, 10_000_000), "classification": "research"},
            {"pattern": "DICOM_SR_{study_id}.dcm", "type": ".dcm", "size_range": (100_000, 1_000_000), "classification": "medical_imaging"},
            {"pattern": "lab_results_{patient_id}_{date}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "clinical"},
            {"pattern": "surgical_video_{procedure}_{date}.mp4", "type": ".mp4", "size_range": (500_000_000, 5_000_000_000), "classification": "surgical"},
            {"pattern": "IRB_approval_{trial_id}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "compliance"},
        ],
        "studies": ["STD-2024-001", "STD-2024-002", "STD-2024-003", "STD-2023-045", "STD-2023-078"],
        "trials": ["NCT-04521", "NCT-04522", "NCT-04890", "NCT-05001", "NCT-05123"],
        "procedures": ["arthroscopy", "laparoscopy", "endoscopy", "biopsy", "catheterization"],
    },
    "media": {
        "departments": ["production", "post_production", "graphics", "audio", "archive"],
        "file_templates": [
            {"pattern": "raw_footage_{project}_{scene}_{take}.mov", "type": ".mov", "size_range": (1_000_000_000, 50_000_000_000), "classification": "raw_footage"},
            {"pattern": "{project}_final_cut_v{ver}.mp4", "type": ".mp4", "size_range": (500_000_000, 10_000_000_000), "classification": "edited"},
            {"pattern": "VFX_{project}_{shot}_comp.exr", "type": ".exr", "size_range": (50_000_000, 500_000_000), "classification": "vfx"},
            {"pattern": "color_grade_{project}_{reel}.dpx", "type": ".dpx", "size_range": (100_000_000, 1_000_000_000), "classification": "color"},
            {"pattern": "audio_mix_{project}_{stem}.wav", "type": ".wav", "size_range": (50_000_000, 500_000_000), "classification": "audio"},
            {"pattern": "thumbnail_{project}_{variant}.psd", "type": ".psd", "size_range": (10_000_000, 100_000_000), "classification": "graphics"},
            {"pattern": "subtitle_{project}_{lang}.srt", "type": ".srt", "size_range": (10_000, 500_000), "classification": "subtitle"},
            {"pattern": "storyboard_{project}_{scene}.pdf", "type": ".pdf", "size_range": (5_000_000, 50_000_000), "classification": "pre_production"},
            {"pattern": "BTS_photo_{project}_{num}.raw", "type": ".raw", "size_range": (20_000_000, 80_000_000), "classification": "photography"},
            {"pattern": "music_license_{track}_{project}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "legal"},
        ],
        "projects": ["Sakura_Documentary", "Tokyo_Nights", "Ocean_Blue", "Mountain_Spirit", "City_Pulse"],
        "scenes": ["opening", "interview_01", "b_roll_sunset", "aerial_city", "closing"],
    },
    "public_sector": {
        "departments": ["records", "legal", "planning", "public_works", "emergency"],
        "file_templates": [
            {"pattern": "permit_application_{type}_{id}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "permit"},
            {"pattern": "council_minutes_{date}.pdf", "type": ".pdf", "size_range": (200_000, 3_000_000), "classification": "governance"},
            {"pattern": "GIS_map_{area}_{layer}.tiff", "type": ".tiff", "size_range": (50_000_000, 500_000_000), "classification": "geospatial"},
            {"pattern": "public_comment_{project}_{id}.pdf", "type": ".pdf", "size_range": (100_000, 2_000_000), "classification": "public_input"},
            {"pattern": "budget_proposal_{dept}_{fy}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "financial"},
            {"pattern": "emergency_plan_{scenario}_{ver}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "emergency"},
            {"pattern": "FOIA_request_{id}_{date}.pdf", "type": ".pdf", "size_range": (500_000, 20_000_000), "classification": "legal"},
            {"pattern": "infrastructure_report_{asset}.pdf", "type": ".pdf", "size_range": (2_000_000, 15_000_000), "classification": "engineering"},
            {"pattern": "census_data_{district}_{year}.csv", "type": ".csv", "size_range": (1_000_000, 50_000_000), "classification": "statistics"},
            {"pattern": "training_cert_{employee}_{course}.pdf", "type": ".pdf", "size_range": (200_000, 1_000_000), "classification": "hr"},
        ],
        "permit_types": ["building", "environmental", "zoning", "demolition", "occupancy"],
        "areas": ["District-1", "District-2", "Downtown", "Industrial-Zone", "Residential-North"],
    },
    "energy": {
        "departments": ["operations", "safety", "environmental", "engineering", "compliance"],
        "file_templates": [
            {"pattern": "well_log_{well_id}_{date}.las", "type": ".las", "size_range": (5_000_000, 50_000_000), "classification": "geological"},
            {"pattern": "seismic_survey_{area}_{line}.segy", "type": ".segy", "size_range": (100_000_000, 5_000_000_000), "classification": "geological"},
            {"pattern": "pipeline_inspection_{segment}_{date}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "inspection"},
            {"pattern": "SCADA_data_{plant}_{date}.csv", "type": ".csv", "size_range": (10_000_000, 100_000_000), "classification": "operations"},
            {"pattern": "environmental_impact_{project}.pdf", "type": ".pdf", "size_range": (10_000_000, 100_000_000), "classification": "environmental"},
            {"pattern": "safety_incident_{id}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "safety"},
            {"pattern": "drone_inspection_{asset}_{date}.mp4", "type": ".mp4", "size_range": (500_000_000, 5_000_000_000), "classification": "inspection"},
            {"pattern": "turbine_performance_{unit}_{month}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "operations"},
            {"pattern": "regulatory_filing_{agency}_{year}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "compliance"},
            {"pattern": "thermal_image_{equipment}_{date}.tiff", "type": ".tiff", "size_range": (10_000_000, 50_000_000), "classification": "inspection"},
        ],
        "wells": ["WL-001", "WL-002", "WL-003", "WL-045", "WL-078"],
        "plants": ["Plant-Alpha", "Plant-Beta", "Offshore-1", "Refinery-East", "Solar-Farm-3"],
        "assets": ["Turbine-01", "Pipeline-A3", "Transformer-12", "Compressor-07", "Tower-15"],
    },
    "legal": {
        "departments": ["litigation", "corporate", "ip", "compliance", "real_estate"],
        "file_templates": [
            {"pattern": "contract_{client}_{contract_type}_{year}.pdf", "type": ".pdf", "size_range": (500_000, 15_000_000), "classification": "contract"},
            {"pattern": "NDA_{counterparty}_{date}_executed.pdf", "type": ".pdf", "size_range": (200_000, 3_000_000), "classification": "confidential"},
            {"pattern": "court_filing_{case_num}_{filing_type}.pdf", "type": ".pdf", "size_range": (1_000_000, 50_000_000), "classification": "litigation"},
            {"pattern": "legal_opinion_{matter}_{date}.docx", "type": ".docx", "size_range": (300_000, 5_000_000), "classification": "privileged"},
            {"pattern": "privilege_log_{case_num}_{date}.xlsx", "type": ".xlsx", "size_range": (200_000, 10_000_000), "classification": "privileged"},
            {"pattern": "deposition_transcript_{witness}_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "litigation"},
            {"pattern": "patent_application_{patent_id}_{ver}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "ip"},
            {"pattern": "lease_agreement_{property}_{year}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "real_estate"},
            {"pattern": "compliance_memo_{regulation}_{date}.docx", "type": ".docx", "size_range": (200_000, 3_000_000), "classification": "compliance"},
            {"pattern": "discovery_production_{case_num}_batch{num}.zip", "type": ".zip", "size_range": (50_000_000, 500_000_000), "classification": "litigation"},
        ],
        "clients": ["Nakamura_Corp", "Watanabe_Holdings", "Ito_Industries", "Kato_Group", "Yoshida_Partners"],
        "matters": ["merger_review", "patent_dispute", "employment_claim", "regulatory_inquiry", "contract_breach"],
        "case_numbers": ["CV-2024-1234", "CV-2024-5678", "CV-2023-9012", "AP-2024-3456", "CR-2024-7890"],
        "witnesses": ["Tanaka_K", "Suzuki_M", "Yamada_T", "Sato_H", "Kobayashi_R"],
        "properties": ["Marunouchi_Tower", "Shibuya_Office", "Osaka_Warehouse", "Nagoya_Plant", "Fukuoka_Center"],
        "contract_types": ["MSA", "SLA", "licensing", "employment", "vendor"],
        "filing_types": ["motion", "brief", "complaint", "answer", "discovery_request"],
        "regulations": ["GDPR", "SOX", "HIPAA", "FCPA", "antitrust"],
    },
    "semiconductor": {
        "departments": ["design", "verification", "fab", "test", "packaging"],
        "file_templates": [
            {"pattern": "{chip}_top_level_{process_node}.gds", "type": ".gds", "size_range": (100_000_000, 5_000_000_000), "classification": "design"},
            {"pattern": "{chip}_timing_{corner}.lib", "type": ".lib", "size_range": (10_000_000, 200_000_000), "classification": "design"},
            {"pattern": "DRC_report_{chip}_{run_id}.rpt", "type": ".rpt", "size_range": (5_000_000, 50_000_000), "classification": "verification"},
            {"pattern": "test_vector_{chip}_{pattern_set}.stil", "type": ".stil", "size_range": (50_000_000, 500_000_000), "classification": "test"},
            {"pattern": "datasheet_{chip}_rev{ver}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "documentation"},
            {"pattern": "{chip}_netlist_{stage}.v", "type": ".v", "size_range": (10_000_000, 100_000_000), "classification": "design"},
            {"pattern": "LVS_report_{chip}_{date}.rpt", "type": ".rpt", "size_range": (5_000_000, 30_000_000), "classification": "verification"},
            {"pattern": "yield_analysis_{wafer_lot}_{date}.xlsx", "type": ".xlsx", "size_range": (1_000_000, 10_000_000), "classification": "fab"},
            {"pattern": "package_design_{chip}_{pkg_type}.mcm", "type": ".mcm", "size_range": (20_000_000, 200_000_000), "classification": "packaging"},
            {"pattern": "simulation_waveform_{chip}_{testbench}.vcd", "type": ".vcd", "size_range": (100_000_000, 2_000_000_000), "classification": "verification"},
        ],
        "chips": ["AX-7200", "NP-4500", "RF-3100", "DSP-8800", "MCU-1600", "GPU-9400"],
        "process_nodes": ["5nm", "7nm", "14nm", "28nm", "45nm"],
        "corners": ["tt_0p85v_25c", "ss_0p75v_m40c", "ff_0p95v_125c", "tt_nom", "sf_0p80v_85c"],
        "wafer_lots": ["LOT-A2401", "LOT-A2402", "LOT-B2401", "LOT-C2401", "LOT-D2401"],
        "pkg_types": ["BGA-484", "QFN-64", "FCBGA-1024", "WLCSP-36", "SiP-module"],
        "stages": ["rtl", "synthesis", "place_route", "signoff"],
    },
    "genomics": {
        "departments": ["sequencing", "bioinformatics", "clinical", "research", "quality"],
        "file_templates": [
            {"pattern": "{sample_id}_{flowcell}_L{lane}_R{read}.fastq.gz", "type": ".fastq.gz", "size_range": (1_000_000_000, 50_000_000_000), "classification": "raw_sequencing"},
            {"pattern": "{sample_id}_variants_{caller}.vcf.gz", "type": ".vcf.gz", "size_range": (50_000_000, 500_000_000), "classification": "variants"},
            {"pattern": "{sample_id}_aligned_{reference}.bam", "type": ".bam", "size_range": (5_000_000_000, 100_000_000_000), "classification": "alignment"},
            {"pattern": "QC_report_{run_id}_{date}.html", "type": ".html", "size_range": (1_000_000, 10_000_000), "classification": "quality"},
            {"pattern": "protocol_{assay_type}_v{ver}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "protocol"},
            {"pattern": "{sample_id}_coverage_{region}.bed", "type": ".bed", "size_range": (10_000_000, 100_000_000), "classification": "analysis"},
            {"pattern": "clinical_report_{patient_id}_{panel}.pdf", "type": ".pdf", "size_range": (1_000_000, 8_000_000), "classification": "clinical"},
            {"pattern": "annotation_{gene_panel}_{build}.gff3", "type": ".gff3", "size_range": (50_000_000, 500_000_000), "classification": "reference"},
            {"pattern": "expression_matrix_{experiment}_{date}.h5", "type": ".h5", "size_range": (100_000_000, 2_000_000_000), "classification": "research"},
            {"pattern": "phylogenetic_tree_{study}_{method}.nwk", "type": ".nwk", "size_range": (100_000, 5_000_000), "classification": "research"},
        ],
        "sample_ids": ["SAMP-001", "SAMP-002", "SAMP-003", "SAMP-044", "SAMP-078", "SAMP-112"],
        "flowcells": ["FC-A01234", "FC-B05678", "FC-C09012", "FC-D03456"],
        "callers": ["gatk_hc", "deepvariant", "strelka2", "freebayes"],
        "references": ["hg38", "GRCh38", "T2T_CHM13", "mm39"],
        "assay_types": ["WGS", "WES", "RNA-seq", "ATAC-seq", "ChIP-seq"],
        "gene_panels": ["onco_500", "cardio_200", "neuro_150", "immuno_300", "rare_disease_1000"],
    },
    "autonomous_driving": {
        "departments": ["perception", "planning", "mapping", "simulation", "safety"],
        "file_templates": [
            {"pattern": "cam_{camera_pos}_{drive_id}_frame{frame_num}.png", "type": ".png", "size_range": (2_000_000, 10_000_000), "classification": "perception"},
            {"pattern": "lidar_{drive_id}_{timestamp}.pcd", "type": ".pcd", "size_range": (10_000_000, 100_000_000), "classification": "perception"},
            {"pattern": "radar_{drive_id}_{radar_pos}_{timestamp}.bin", "type": ".bin", "size_range": (1_000_000, 20_000_000), "classification": "perception"},
            {"pattern": "hdmap_{region}_{tile_id}_v{ver}.bin", "type": ".bin", "size_range": (50_000_000, 500_000_000), "classification": "mapping"},
            {"pattern": "scenario_{test_type}_{scenario_id}.yaml", "type": ".yaml", "size_range": (100_000, 2_000_000), "classification": "simulation"},
            {"pattern": "annotation_{drive_id}_{label_type}.json", "type": ".json", "size_range": (5_000_000, 50_000_000), "classification": "perception"},
            {"pattern": "trajectory_log_{vehicle_id}_{date}.csv", "type": ".csv", "size_range": (10_000_000, 100_000_000), "classification": "planning"},
            {"pattern": "safety_report_{test_type}_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "safety"},
            {"pattern": "sim_replay_{scenario_id}_{run}.rosbag", "type": ".rosbag", "size_range": (500_000_000, 10_000_000_000), "classification": "simulation"},
            {"pattern": "calibration_{vehicle_id}_{sensor_suite}.json", "type": ".json", "size_range": (100_000, 1_000_000), "classification": "calibration"},
        ],
        "camera_positions": ["front", "front_left", "front_right", "rear", "rear_left", "rear_right"],
        "radar_positions": ["front", "rear", "left", "right"],
        "drive_ids": ["DRV-20240301-001", "DRV-20240315-042", "DRV-20240401-003", "DRV-20240412-017"],
        "regions": ["Tokyo_Shibuya", "Osaka_Umeda", "Nagoya_Station", "Yokohama_MM21", "Fukuoka_Hakata"],
        "vehicle_ids": ["VEH-001", "VEH-002", "VEH-003", "VEH-004", "VEH-005"],
        "test_types": ["highway_merge", "intersection", "pedestrian_crossing", "parking", "emergency_brake"],
        "label_types": ["3d_bbox", "semantic_seg", "lane_marking", "traffic_sign"],
    },
    "construction": {
        "departments": ["architecture", "structural", "mep", "site", "safety"],
        "file_templates": [
            {"pattern": "{project}_IFC_model_{discipline}_v{ver}.ifc", "type": ".ifc", "size_range": (50_000_000, 2_000_000_000), "classification": "bim"},
            {"pattern": "drawing_{project}_{discipline}_{sheet_num}.dwg", "type": ".dwg", "size_range": (5_000_000, 50_000_000), "classification": "design"},
            {"pattern": "site_photo_{project}_{zone}_{date}.jpg", "type": ".jpg", "size_range": (3_000_000, 15_000_000), "classification": "documentation"},
            {"pattern": "safety_report_{project}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "safety"},
            {"pattern": "specification_{project}_{section}.pdf", "type": ".pdf", "size_range": (2_000_000, 30_000_000), "classification": "specification"},
            {"pattern": "RFI_{project}_{rfi_num}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "coordination"},
            {"pattern": "schedule_{project}_{phase}.mpp", "type": ".mpp", "size_range": (1_000_000, 10_000_000), "classification": "planning"},
            {"pattern": "clash_report_{project}_{date}.html", "type": ".html", "size_range": (2_000_000, 20_000_000), "classification": "coordination"},
            {"pattern": "soil_investigation_{project}_{borehole}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "geotechnical"},
            {"pattern": "progress_drone_{project}_{date}.mp4", "type": ".mp4", "size_range": (200_000_000, 2_000_000_000), "classification": "documentation"},
        ],
        "projects": ["Minato_Tower", "Shibuya_Station_Redevelopment", "Osaka_Bay_Bridge", "Nagoya_Hospital", "Fukuoka_Arena"],
        "disciplines": ["architectural", "structural", "mechanical", "electrical", "plumbing"],
        "zones": ["Zone_A", "Zone_B", "Zone_C", "Basement", "Rooftop"],
        "sections": ["div_03_concrete", "div_05_metals", "div_09_finishes", "div_23_hvac", "div_26_electrical"],
    },
    "retail": {
        "departments": ["photography", "design", "marketing", "catalog", "ecommerce"],
        "file_templates": [
            {"pattern": "product_{sku}_{angle}_{bg}.tiff", "type": ".tiff", "size_range": (20_000_000, 200_000_000), "classification": "product_photo"},
            {"pattern": "lifestyle_{campaign}_{scene}_{num}.raw", "type": ".raw", "size_range": (30_000_000, 100_000_000), "classification": "lifestyle"},
            {"pattern": "brand_asset_{brand}_{asset_type}_{variant}.ai", "type": ".ai", "size_range": (5_000_000, 50_000_000), "classification": "brand"},
            {"pattern": "catalog_{season}_{category}_page{num}.indd", "type": ".indd", "size_range": (20_000_000, 200_000_000), "classification": "catalog"},
            {"pattern": "banner_{campaign}_{size}_{variant}.psd", "type": ".psd", "size_range": (5_000_000, 50_000_000), "classification": "marketing"},
            {"pattern": "product_video_{sku}_{ver}.mp4", "type": ".mp4", "size_range": (100_000_000, 2_000_000_000), "classification": "video"},
            {"pattern": "lookbook_{season}_{collection}.pdf", "type": ".pdf", "size_range": (10_000_000, 100_000_000), "classification": "catalog"},
            {"pattern": "social_media_{campaign}_{platform}_{num}.jpg", "type": ".jpg", "size_range": (1_000_000, 10_000_000), "classification": "marketing"},
            {"pattern": "packaging_design_{sku}_{ver}.ai", "type": ".ai", "size_range": (10_000_000, 80_000_000), "classification": "design"},
            {"pattern": "model_release_{model_name}_{date}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "legal"},
        ],
        "skus": ["SKU-A1001", "SKU-B2002", "SKU-C3003", "SKU-D4004", "SKU-E5005", "SKU-F6006"],
        "campaigns": ["Summer_2024", "Winter_2024", "Spring_2025", "Holiday_Special", "New_Year"],
        "brands": ["MainBrand", "SubLabel_A", "Premium_Line", "Eco_Collection"],
        "seasons": ["SS24", "AW24", "SS25", "AW25"],
        "categories": ["apparel", "accessories", "footwear", "home", "beauty"],
        "angles": ["front", "back", "side", "detail", "flat_lay"],
        "sizes": ["728x90", "300x250", "1080x1080", "1200x628", "1920x1080"],
        "platforms": ["instagram", "facebook", "twitter", "line", "tiktok"],
    },
    "logistics": {
        "departments": ["shipping", "customs", "warehouse", "fleet", "compliance"],
        "file_templates": [
            {"pattern": "BOL_{shipment_id}_{carrier}_{date}.pdf", "type": ".pdf", "size_range": (200_000, 3_000_000), "classification": "shipping"},
            {"pattern": "customs_declaration_{shipment_id}_{country}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "customs"},
            {"pattern": "delivery_proof_{shipment_id}_{date}.jpg", "type": ".jpg", "size_range": (1_000_000, 8_000_000), "classification": "delivery"},
            {"pattern": "manifest_{vessel}_{voyage}_{date}.xlsx", "type": ".xlsx", "size_range": (500_000, 10_000_000), "classification": "shipping"},
            {"pattern": "tracking_report_{route}_{month}.csv", "type": ".csv", "size_range": (5_000_000, 50_000_000), "classification": "operations"},
            {"pattern": "warehouse_inventory_{location}_{date}.xlsx", "type": ".xlsx", "size_range": (1_000_000, 20_000_000), "classification": "warehouse"},
            {"pattern": "fleet_maintenance_{vehicle_id}_{date}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "fleet"},
            {"pattern": "dangerous_goods_{shipment_id}_DGD.pdf", "type": ".pdf", "size_range": (300_000, 3_000_000), "classification": "compliance"},
            {"pattern": "insurance_certificate_{shipment_id}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "compliance"},
            {"pattern": "route_optimization_{route}_{date}.json", "type": ".json", "size_range": (1_000_000, 10_000_000), "classification": "planning"},
        ],
        "shipment_ids": ["SHP-2024-00123", "SHP-2024-00456", "SHP-2024-00789", "SHP-2024-01012", "SHP-2024-01345"],
        "carriers": ["Nippon_Express", "Yamato_Transport", "Sagawa_Express", "Maersk", "DHL"],
        "vessels": ["MV_Pacific_Star", "MV_Tokyo_Maru", "MV_Ocean_Bridge", "MV_Asia_Express"],
        "routes": ["Tokyo-Shanghai", "Osaka-LA", "Nagoya-Singapore", "Yokohama-Rotterdam", "Kobe-Sydney"],
        "locations": ["WH-Tokyo-01", "WH-Osaka-02", "WH-Nagoya-03", "WH-Yokohama-04", "DC-Chiba-01"],
        "countries": ["JP", "CN", "US", "SG", "DE", "AU"],
    },
    "education": {
        "departments": ["research", "teaching", "administration", "library", "grants"],
        "file_templates": [
            {"pattern": "paper_{author}_{topic}_{year}_draft{ver}.docx", "type": ".docx", "size_range": (1_000_000, 20_000_000), "classification": "research"},
            {"pattern": "thesis_{student}_{degree}_{year}.pdf", "type": ".pdf", "size_range": (5_000_000, 100_000_000), "classification": "research"},
            {"pattern": "dataset_{project}_{experiment}_{date}.csv", "type": ".csv", "size_range": (10_000_000, 500_000_000), "classification": "research_data"},
            {"pattern": "course_material_{course_code}_{module}_{semester}.pdf", "type": ".pdf", "size_range": (2_000_000, 30_000_000), "classification": "teaching"},
            {"pattern": "grant_proposal_{funder}_{project}_{year}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "grants"},
            {"pattern": "lecture_recording_{course_code}_{week}_{topic}.mp4", "type": ".mp4", "size_range": (200_000_000, 3_000_000_000), "classification": "teaching"},
            {"pattern": "peer_review_{journal}_{manuscript_id}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "research"},
            {"pattern": "lab_notebook_{researcher}_{project}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "research_data"},
            {"pattern": "accreditation_report_{program}_{year}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "administration"},
            {"pattern": "student_records_{department}_{semester}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "administration"},
        ],
        "authors": ["Prof_Tanaka", "Dr_Suzuki", "Prof_Yamamoto", "Dr_Watanabe", "Prof_Ito"],
        "students": ["Sato_M", "Takahashi_K", "Nakamura_Y", "Kobayashi_A", "Kato_S"],
        "course_codes": ["CS-401", "BIO-302", "PHY-501", "ENG-201", "MATH-601"],
        "funders": ["JSPS", "JST", "MEXT", "AMED", "NEDO"],
        "journals": ["Nature", "Science", "PNAS", "PLoS_ONE", "IEEE_Trans"],
        "topics": ["machine_learning", "quantum_computing", "genomics", "materials_science", "climate_modeling"],
    },
    "insurance": {
        "departments": ["claims", "underwriting", "actuarial", "fraud", "compliance"],
        "file_templates": [
            {"pattern": "damage_photo_{claim_id}_{angle}_{num}.jpg", "type": ".jpg", "size_range": (2_000_000, 15_000_000), "classification": "claims"},
            {"pattern": "policy_document_{policy_id}_{type}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "underwriting"},
            {"pattern": "claim_form_{claim_id}_{date}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "claims"},
            {"pattern": "assessment_report_{claim_id}_{assessor}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "claims"},
            {"pattern": "surveillance_video_{claim_id}_{date}.mp4", "type": ".mp4", "size_range": (100_000_000, 2_000_000_000), "classification": "fraud"},
            {"pattern": "actuarial_model_{product}_{year}.xlsx", "type": ".xlsx", "size_range": (5_000_000, 50_000_000), "classification": "actuarial"},
            {"pattern": "risk_score_{portfolio}_{quarter}.csv", "type": ".csv", "size_range": (1_000_000, 20_000_000), "classification": "actuarial"},
            {"pattern": "fraud_alert_{claim_id}_{date}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "fraud"},
            {"pattern": "regulatory_filing_{regulator}_{quarter}.pdf", "type": ".pdf", "size_range": (2_000_000, 15_000_000), "classification": "compliance"},
            {"pattern": "reinsurance_treaty_{treaty_id}_{year}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "underwriting"},
        ],
        "claim_ids": ["CLM-2024-10001", "CLM-2024-10002", "CLM-2024-20045", "CLM-2024-30078", "CLM-2023-50123"],
        "policy_ids": ["POL-AUTO-001234", "POL-HOME-005678", "POL-LIFE-009012", "POL-COMM-003456"],
        "assessors": ["Adj_Tanaka", "Adj_Suzuki", "Adj_Yamada", "Adj_Sato", "Adj_Kato"],
        "products": ["auto_comprehensive", "home_fire", "life_term", "commercial_liability", "health_group"],
        "treaty_ids": ["TRT-2024-A01", "TRT-2024-B02", "TRT-2024-C03"],
        "angles": ["front", "rear", "left", "right", "interior", "overhead"],
    },
    "defense": {
        "departments": ["intelligence", "operations", "logistics", "communications", "cyber"],
        "file_templates": [
            {"pattern": "satellite_imagery_{region}_{date}_{band}.tiff", "type": ".tiff", "size_range": (100_000_000, 5_000_000_000), "classification": "imagery"},
            {"pattern": "mission_report_{operation}_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "operations"},
            {"pattern": "equipment_log_{unit}_{equipment}_{month}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "logistics"},
            {"pattern": "comms_intercept_{sector}_{date}_{id}.bin", "type": ".bin", "size_range": (10_000_000, 500_000_000), "classification": "sigint"},
            {"pattern": "terrain_map_{region}_{resolution}.dt2", "type": ".dt2", "size_range": (50_000_000, 2_000_000_000), "classification": "geospatial"},
            {"pattern": "threat_assessment_{region}_{date}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "intelligence"},
            {"pattern": "logistics_manifest_{unit}_{deployment}.xlsx", "type": ".xlsx", "size_range": (1_000_000, 10_000_000), "classification": "logistics"},
            {"pattern": "cyber_incident_{incident_id}_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 15_000_000), "classification": "cyber"},
            {"pattern": "training_exercise_{exercise_name}_{date}.pdf", "type": ".pdf", "size_range": (5_000_000, 50_000_000), "classification": "operations"},
            {"pattern": "network_capture_{sector}_{date}.pcap", "type": ".pcap", "size_range": (100_000_000, 5_000_000_000), "classification": "cyber"},
        ],
        "regions": ["Pacific_West", "Indo_Pacific", "Northern_Theater", "Southern_Islands", "Central_Command"],
        "operations": ["OP_Guardian", "OP_Shield", "OP_Horizon", "OP_Sentinel", "OP_Trident"],
        "units": ["1st_Div", "3rd_Brigade", "7th_Fleet", "Air_Wing_5", "Cyber_Group_1"],
        "sectors": ["Sector_Alpha", "Sector_Bravo", "Sector_Charlie", "Sector_Delta"],
        "exercise_names": ["Pacific_Shield", "Iron_Fist", "Keen_Sword", "Orient_Shield", "Cobra_Gold"],
        "bands": ["visible", "infrared", "SAR", "multispectral", "hyperspectral"],
        "resolutions": ["1m", "5m", "10m", "30m", "90m"],
    },
    "smart_city": {
        "departments": ["planning", "utilities", "transport", "emergency", "environment"],
        "file_templates": [
            {"pattern": "GIS_map_{city_zone}_{layer}_{date}.geojson", "type": ".geojson", "size_range": (10_000_000, 500_000_000), "classification": "geospatial"},
            {"pattern": "sensor_data_{sensor_type}_{location}_{date}.csv", "type": ".csv", "size_range": (5_000_000, 100_000_000), "classification": "iot"},
            {"pattern": "traffic_report_{corridor}_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 15_000_000), "classification": "transport"},
            {"pattern": "emergency_plan_{disaster_type}_{zone}_{ver}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "emergency"},
            {"pattern": "environmental_assessment_{project}_{date}.pdf", "type": ".pdf", "size_range": (5_000_000, 50_000_000), "classification": "environment"},
            {"pattern": "utility_usage_{utility_type}_{district}_{month}.csv", "type": ".csv", "size_range": (2_000_000, 20_000_000), "classification": "utilities"},
            {"pattern": "urban_plan_{zone}_{phase}_v{ver}.dwg", "type": ".dwg", "size_range": (10_000_000, 100_000_000), "classification": "planning"},
            {"pattern": "cctv_footage_{location}_{date}.mp4", "type": ".mp4", "size_range": (500_000_000, 10_000_000_000), "classification": "security"},
            {"pattern": "air_quality_{station}_{date}.json", "type": ".json", "size_range": (1_000_000, 10_000_000), "classification": "environment"},
            {"pattern": "citizen_feedback_{topic}_{month}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "governance"},
        ],
        "city_zones": ["Central_Ward", "Harbor_District", "Tech_Park", "Residential_North", "Industrial_South"],
        "sensor_types": ["air_quality", "traffic_flow", "noise_level", "water_quality", "energy_meter"],
        "corridors": ["Route_1", "Ring_Road", "Metro_Line_A", "Highway_3", "Waterfront_Ave"],
        "disaster_types": ["earthquake", "flood", "typhoon", "tsunami", "fire"],
        "utility_types": ["electricity", "water", "gas", "sewage", "telecom"],
        "layers": ["buildings", "roads", "utilities", "green_space", "zoning"],
        "stations": ["AQ-Station-01", "AQ-Station-02", "AQ-Station-03", "AQ-Station-04", "AQ-Station-05"],
    },
    "gaming": {
        "departments": ["art", "engineering", "audio", "design", "qa"],
        "file_templates": [
            {"pattern": "{asset_name}_model_LOD{lod}.fbx", "type": ".fbx", "size_range": (10_000_000, 500_000_000), "classification": "3d_model"},
            {"pattern": "{asset_name}_texture_{tex_type}_{resolution}.png", "type": ".png", "size_range": (5_000_000, 100_000_000), "classification": "texture"},
            {"pattern": "{character}_anim_{action}.fbx", "type": ".fbx", "size_range": (5_000_000, 100_000_000), "classification": "animation"},
            {"pattern": "sfx_{sound_category}_{sound_name}.wav", "type": ".wav", "size_range": (1_000_000, 50_000_000), "classification": "audio"},
            {"pattern": "level_{world}_{area}_design.umap", "type": ".umap", "size_range": (50_000_000, 2_000_000_000), "classification": "level_design"},
            {"pattern": "shader_{material_type}_{effect}.hlsl", "type": ".hlsl", "size_range": (10_000, 500_000), "classification": "shader"},
            {"pattern": "music_{zone}_{mood}_{ver}.ogg", "type": ".ogg", "size_range": (5_000_000, 50_000_000), "classification": "audio"},
            {"pattern": "concept_art_{character}_{pose}_{num}.psd", "type": ".psd", "size_range": (20_000_000, 200_000_000), "classification": "concept"},
            {"pattern": "qa_report_{build}_{platform}_{date}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "qa"},
            {"pattern": "cutscene_{chapter}_{scene}_v{ver}.mp4", "type": ".mp4", "size_range": (200_000_000, 5_000_000_000), "classification": "cinematic"},
        ],
        "asset_names": ["dragon_boss", "medieval_castle", "space_station", "forest_tree_01", "weapon_sword_epic", "vehicle_hover_bike"],
        "characters": ["hero_knight", "villain_mage", "npc_merchant", "companion_wolf", "boss_dragon"],
        "tex_types": ["albedo", "normal", "roughness", "metallic", "emissive", "ao"],
        "sound_categories": ["weapon", "ambient", "ui", "creature", "environment"],
        "worlds": ["overworld", "dungeon", "sky_realm", "underwater", "volcano"],
        "material_types": ["pbr_standard", "water", "foliage", "skin", "crystal", "lava"],
        "platforms": ["PC", "PS5", "Xbox", "Switch", "Mobile"],
        "builds": ["v0.9.1", "v0.9.2", "v1.0.0-rc1", "v1.0.0-rc2", "v1.0.0"],
    },
    "sap_erp": {
        "departments": ["finance", "procurement", "production", "sales", "hr"],
        "file_templates": [
            {"pattern": "invoice_{company_code}_{doc_num}_{date}.pdf", "type": ".pdf", "size_range": (200_000, 5_000_000), "classification": "finance"},
            {"pattern": "purchase_order_{po_num}_{vendor}_{date}.pdf", "type": ".pdf", "size_range": (300_000, 3_000_000), "classification": "procurement"},
            {"pattern": "delivery_note_{delivery_num}_{date}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "logistics"},
            {"pattern": "production_order_{order_num}_{material}.pdf", "type": ".pdf", "size_range": (300_000, 5_000_000), "classification": "production"},
            {"pattern": "HR_document_{employee_id}_{doc_type}.pdf", "type": ".pdf", "size_range": (200_000, 3_000_000), "classification": "hr"},
            {"pattern": "GL_posting_{company_code}_{period}_{year}.xlsx", "type": ".xlsx", "size_range": (1_000_000, 20_000_000), "classification": "finance"},
            {"pattern": "vendor_evaluation_{vendor}_{quarter}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "procurement"},
            {"pattern": "BOM_change_{material}_{ecn_num}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "production"},
            {"pattern": "sales_order_{so_num}_{customer}_{date}.pdf", "type": ".pdf", "size_range": (200_000, 3_000_000), "classification": "sales"},
            {"pattern": "payroll_report_{company_code}_{period}.xlsx", "type": ".xlsx", "size_range": (1_000_000, 10_000_000), "classification": "hr"},
        ],
        "company_codes": ["1000", "2000", "3000", "4000", "5000"],
        "vendors": ["VND-10001", "VND-10002", "VND-20003", "VND-30004", "VND-40005"],
        "materials": ["MAT-100001", "MAT-200002", "MAT-300003", "MAT-400004", "MAT-500005"],
        "customers": ["CUST-A001", "CUST-B002", "CUST-C003", "CUST-D004", "CUST-E005"],
        "doc_types": ["contract", "certificate", "evaluation", "onboarding", "termination"],
        "periods": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
    },
    "life_sciences": {
        "departments": ["discovery", "preclinical", "clinical", "regulatory", "manufacturing"],
        "file_templates": [
            {"pattern": "assay_results_{compound}_{assay_type}_{date}.xlsx", "type": ".xlsx", "size_range": (1_000_000, 20_000_000), "classification": "discovery"},
            {"pattern": "compound_structure_{compound}_{ver}.sdf", "type": ".sdf", "size_range": (100_000, 5_000_000), "classification": "chemistry"},
            {"pattern": "microscopy_{sample}_{magnification}_{date}.tiff", "type": ".tiff", "size_range": (50_000_000, 2_000_000_000), "classification": "imaging"},
            {"pattern": "regulatory_submission_{submission_type}_{compound}_{date}.pdf", "type": ".pdf", "size_range": (10_000_000, 200_000_000), "classification": "regulatory"},
            {"pattern": "batch_record_{product}_{batch_num}_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "manufacturing"},
            {"pattern": "toxicology_report_{compound}_{study_type}.pdf", "type": ".pdf", "size_range": (5_000_000, 50_000_000), "classification": "preclinical"},
            {"pattern": "clinical_data_{trial_id}_{visit}_{date}.csv", "type": ".csv", "size_range": (5_000_000, 100_000_000), "classification": "clinical"},
            {"pattern": "stability_study_{product}_{condition}_{timepoint}.xlsx", "type": ".xlsx", "size_range": (1_000_000, 10_000_000), "classification": "manufacturing"},
            {"pattern": "patent_filing_{compound}_{jurisdiction}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "ip"},
            {"pattern": "HPLC_chromatogram_{sample}_{method}_{date}.cdf", "type": ".cdf", "size_range": (5_000_000, 50_000_000), "classification": "analytics"},
        ],
        "compounds": ["CPD-001", "CPD-002", "CPD-003", "CPD-044", "CPD-078", "CPD-112"],
        "assay_types": ["IC50", "EC50", "binding", "ADME", "cytotoxicity", "selectivity"],
        "submission_types": ["IND", "NDA", "BLA", "ANDA", "sNDA"],
        "study_types": ["acute_tox", "chronic_tox", "carcinogenicity", "reproductive", "genotoxicity"],
        "products": ["Drug-A", "Drug-B", "Biologic-C", "Vaccine-D", "Gene-Therapy-E"],
        "conditions": ["25C_60RH", "30C_65RH", "40C_75RH", "5C", "minus20C"],
        "magnifications": ["10x", "20x", "40x", "63x", "100x"],
        "methods": ["RP-HPLC", "SEC", "IEX", "HILIC", "CE"],
    },
}


def generate_file_name(template: dict, industry_data: dict) -> str:
    """Generate a realistic file name from a template."""
    pattern = template["pattern"]

    # Common substitutions
    replacements = {
        "{part_num}": str(random.randint(1000, 9999)),
        "{ver}": str(random.randint(1, 5)),
        "{date}": (datetime.now() - timedelta(days=random.randint(1, 730))).strftime("%Y%m%d"),
        "{month}": (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m"),
        "{year}": str(random.choice([2022, 2023, 2024])),
        "{quarter}": str(random.randint(1, 4)),
        "{id}": f"{random.randint(1000, 9999):04d}",
        "{num}": f"{random.randint(1, 999):03d}",
        "{lang}": random.choice(["ja", "en", "zh", "ko"]),
        "{take}": f"T{random.randint(1, 12):02d}",
        "{slice}": f"S{random.randint(1, 200):03d}",
        "{sequence}": random.choice(["T1", "T2", "FLAIR", "DWI", "ADC"]),
        "{stem}": random.choice(["dialogue", "music", "sfx", "ambience", "full_mix"]),
        "{variant}": random.choice(["A", "B", "C", "wide", "square"]),
        "{reel}": f"R{random.randint(1, 10):02d}",
        "{shot}": f"SH{random.randint(100, 999)}",
        "{fy}": f"FY{random.choice([2023, 2024, 2025])}",
        "{timestamp}": f"{random.randint(1700000000, 1710000000)}",
        "{frame_num}": f"{random.randint(0, 99999):06d}",
        "{lod}": str(random.randint(0, 3)),
        "{resolution}": random.choice(["1k", "2k", "4k", "8k"]),
        "{read}": str(random.choice([1, 2])),
        "{lane}": f"{random.randint(1, 8):03d}",
    }

    # Industry-specific substitutions
    if "components" in industry_data:
        replacements["{component}"] = random.choice(industry_data["components"])
    if "products" in industry_data:
        replacements["{product}"] = random.choice(industry_data["products"])
    if "equipment" in industry_data:
        replacements["{equipment}"] = random.choice(industry_data["equipment"])
    if "areas" in industry_data:
        replacements["{area}"] = random.choice(industry_data["areas"])
    if "clients" in industry_data:
        replacements["{client}"] = random.choice(industry_data["clients"])
        replacements["{counterparty}"] = random.choice(industry_data["clients"])
    if "portfolios" in industry_data:
        replacements["{portfolio}"] = random.choice(industry_data["portfolios"])
    if "regulators" in industry_data:
        replacements["{regulator}"] = random.choice(industry_data["regulators"])
        replacements["{agency}"] = random.choice(industry_data["regulators"])
    if "studies" in industry_data:
        replacements["{study_id}"] = random.choice(industry_data["studies"])
    if "trials" in industry_data:
        replacements["{trial_id}"] = random.choice(industry_data["trials"])
    if "procedures" in industry_data:
        replacements["{procedure}"] = random.choice(industry_data["procedures"])
    if "projects" in industry_data:
        replacements["{project}"] = random.choice(industry_data["projects"])
    if "scenes" in industry_data:
        replacements["{scene}"] = random.choice(industry_data["scenes"])
    if "wells" in industry_data:
        replacements["{well_id}"] = random.choice(industry_data["wells"])
    if "plants" in industry_data:
        replacements["{plant}"] = random.choice(industry_data["plants"])
    if "assets" in industry_data:
        replacements["{asset}"] = random.choice(industry_data["assets"])
    if "permit_types" in industry_data:
        replacements["{type}"] = random.choice(industry_data["permit_types"])
    # Legal industry
    if "matters" in industry_data:
        replacements["{matter}"] = random.choice(industry_data["matters"])
    if "case_numbers" in industry_data:
        replacements["{case_num}"] = random.choice(industry_data["case_numbers"])
    if "witnesses" in industry_data:
        replacements["{witness}"] = random.choice(industry_data["witnesses"])
    if "properties" in industry_data:
        replacements["{property}"] = random.choice(industry_data["properties"])
    if "contract_types" in industry_data:
        replacements["{contract_type}"] = random.choice(industry_data["contract_types"])
    if "filing_types" in industry_data:
        replacements["{filing_type}"] = random.choice(industry_data["filing_types"])
    if "regulations" in industry_data:
        replacements["{regulation}"] = random.choice(industry_data["regulations"])
    # Semiconductor industry
    if "chips" in industry_data:
        replacements["{chip}"] = random.choice(industry_data["chips"])
    if "process_nodes" in industry_data:
        replacements["{process_node}"] = random.choice(industry_data["process_nodes"])
    if "corners" in industry_data:
        replacements["{corner}"] = random.choice(industry_data["corners"])
    if "wafer_lots" in industry_data:
        replacements["{wafer_lot}"] = random.choice(industry_data["wafer_lots"])
    if "pkg_types" in industry_data:
        replacements["{pkg_type}"] = random.choice(industry_data["pkg_types"])
    if "stages" in industry_data:
        replacements["{stage}"] = random.choice(industry_data["stages"])
    # Genomics industry
    if "sample_ids" in industry_data:
        replacements["{sample_id}"] = random.choice(industry_data["sample_ids"])
        replacements["{sample}"] = random.choice(industry_data["sample_ids"])
    if "flowcells" in industry_data:
        replacements["{flowcell}"] = random.choice(industry_data["flowcells"])
    if "callers" in industry_data:
        replacements["{caller}"] = random.choice(industry_data["callers"])
    if "references" in industry_data:
        replacements["{reference}"] = random.choice(industry_data["references"])
    if "assay_types" in industry_data:
        replacements["{assay_type}"] = random.choice(industry_data["assay_types"])
    if "gene_panels" in industry_data:
        replacements["{gene_panel}"] = random.choice(industry_data["gene_panels"])
        replacements["{panel}"] = random.choice(industry_data["gene_panels"])
    # Autonomous driving industry
    if "camera_positions" in industry_data:
        replacements["{camera_pos}"] = random.choice(industry_data["camera_positions"])
    if "radar_positions" in industry_data:
        replacements["{radar_pos}"] = random.choice(industry_data["radar_positions"])
    if "drive_ids" in industry_data:
        replacements["{drive_id}"] = random.choice(industry_data["drive_ids"])
    if "regions" in industry_data:
        replacements["{region}"] = random.choice(industry_data["regions"])
    if "vehicle_ids" in industry_data:
        replacements["{vehicle_id}"] = random.choice(industry_data["vehicle_ids"])
    if "test_types" in industry_data:
        replacements["{test_type}"] = random.choice(industry_data["test_types"])
    if "label_types" in industry_data:
        replacements["{label_type}"] = random.choice(industry_data["label_types"])
    # Autonomous driving - additional
    replacements.setdefault("{sensor_suite}", random.choice(["lidar_camera_v1", "full_sensor_v2", "camera_only_v1", "lidar_radar_v3"]))
    # Construction industry
    if "disciplines" in industry_data:
        replacements["{discipline}"] = random.choice(industry_data["disciplines"])
    if "zones" in industry_data:
        replacements["{zone}"] = random.choice(industry_data["zones"])
    if "sections" in industry_data:
        replacements["{section}"] = random.choice(industry_data["sections"])
    # Retail industry
    if "skus" in industry_data:
        replacements["{sku}"] = random.choice(industry_data["skus"])
    if "campaigns" in industry_data:
        replacements["{campaign}"] = random.choice(industry_data["campaigns"])
    if "brands" in industry_data:
        replacements["{brand}"] = random.choice(industry_data["brands"])
    if "seasons" in industry_data:
        replacements["{season}"] = random.choice(industry_data["seasons"])
    if "categories" in industry_data:
        replacements["{category}"] = random.choice(industry_data["categories"])
    if "angles" in industry_data:
        replacements["{angle}"] = random.choice(industry_data["angles"])
    if "sizes" in industry_data:
        replacements["{size}"] = random.choice(industry_data["sizes"])
    if "platforms" in industry_data:
        replacements["{platform}"] = random.choice(industry_data["platforms"])
    # Logistics industry
    if "shipment_ids" in industry_data:
        replacements["{shipment_id}"] = random.choice(industry_data["shipment_ids"])
    if "carriers" in industry_data:
        replacements["{carrier}"] = random.choice(industry_data["carriers"])
    if "vessels" in industry_data:
        replacements["{vessel}"] = random.choice(industry_data["vessels"])
        replacements["{voyage}"] = f"V{random.randint(100, 999)}"
    if "routes" in industry_data:
        replacements["{route}"] = random.choice(industry_data["routes"])
    if "locations" in industry_data:
        replacements["{location}"] = random.choice(industry_data["locations"])
    if "countries" in industry_data:
        replacements["{country}"] = random.choice(industry_data["countries"])
    # Education industry
    if "authors" in industry_data:
        replacements["{author}"] = random.choice(industry_data["authors"])
    if "students" in industry_data:
        replacements["{student}"] = random.choice(industry_data["students"])
    if "course_codes" in industry_data:
        replacements["{course_code}"] = random.choice(industry_data["course_codes"])
    if "funders" in industry_data:
        replacements["{funder}"] = random.choice(industry_data["funders"])
    if "journals" in industry_data:
        replacements["{journal}"] = random.choice(industry_data["journals"])
    if "topics" in industry_data:
        replacements["{topic}"] = random.choice(industry_data["topics"])
    # Insurance industry
    if "claim_ids" in industry_data:
        replacements["{claim_id}"] = random.choice(industry_data["claim_ids"])
    if "policy_ids" in industry_data:
        replacements["{policy_id}"] = random.choice(industry_data["policy_ids"])
    if "assessors" in industry_data:
        replacements["{assessor}"] = random.choice(industry_data["assessors"])
    if "treaty_ids" in industry_data:
        replacements["{treaty_id}"] = random.choice(industry_data["treaty_ids"])
    # Defense industry
    if "operations" in industry_data:
        replacements["{operation}"] = random.choice(industry_data["operations"])
    if "units" in industry_data:
        replacements["{unit}"] = random.choice(industry_data["units"])
    if "sectors" in industry_data:
        replacements["{sector}"] = random.choice(industry_data["sectors"])
    if "exercise_names" in industry_data:
        replacements["{exercise_name}"] = random.choice(industry_data["exercise_names"])
    if "bands" in industry_data:
        replacements["{band}"] = random.choice(industry_data["bands"])
    if "resolutions" in industry_data:
        replacements["{resolution}"] = random.choice(industry_data["resolutions"])
    # Smart city industry
    if "city_zones" in industry_data:
        replacements["{city_zone}"] = random.choice(industry_data["city_zones"])
    if "sensor_types" in industry_data:
        replacements["{sensor_type}"] = random.choice(industry_data["sensor_types"])
    if "corridors" in industry_data:
        replacements["{corridor}"] = random.choice(industry_data["corridors"])
    if "disaster_types" in industry_data:
        replacements["{disaster_type}"] = random.choice(industry_data["disaster_types"])
    if "utility_types" in industry_data:
        replacements["{utility_type}"] = random.choice(industry_data["utility_types"])
    if "layers" in industry_data:
        replacements["{layer}"] = random.choice(industry_data["layers"])
    if "stations" in industry_data:
        replacements["{station}"] = random.choice(industry_data["stations"])
    # Gaming industry
    if "asset_names" in industry_data:
        replacements["{asset_name}"] = random.choice(industry_data["asset_names"])
    if "characters" in industry_data:
        replacements["{character}"] = random.choice(industry_data["characters"])
    if "tex_types" in industry_data:
        replacements["{tex_type}"] = random.choice(industry_data["tex_types"])
    if "sound_categories" in industry_data:
        replacements["{sound_category}"] = random.choice(industry_data["sound_categories"])
    if "worlds" in industry_data:
        replacements["{world}"] = random.choice(industry_data["worlds"])
    if "material_types" in industry_data:
        replacements["{material_type}"] = random.choice(industry_data["material_types"])
    if "builds" in industry_data:
        replacements["{build}"] = random.choice(industry_data["builds"])
    # SAP ERP industry
    if "company_codes" in industry_data:
        replacements["{company_code}"] = random.choice(industry_data["company_codes"])
    if "vendors" in industry_data:
        replacements["{vendor}"] = random.choice(industry_data["vendors"])
    if "materials" in industry_data:
        replacements["{material}"] = random.choice(industry_data["materials"])
    if "customers" in industry_data:
        replacements["{customer}"] = random.choice(industry_data["customers"])
    if "doc_types" in industry_data:
        replacements["{doc_type}"] = random.choice(industry_data["doc_types"])
    if "periods" in industry_data:
        replacements["{period}"] = random.choice(industry_data["periods"])
    # Life sciences industry
    if "compounds" in industry_data:
        replacements["{compound}"] = random.choice(industry_data["compounds"])
    if "submission_types" in industry_data:
        replacements["{submission_type}"] = random.choice(industry_data["submission_types"])
    if "study_types" in industry_data:
        replacements["{study_type}"] = random.choice(industry_data["study_types"])
    if "conditions" in industry_data:
        replacements["{condition}"] = random.choice(industry_data["conditions"])
    if "magnifications" in industry_data:
        replacements["{magnification}"] = random.choice(industry_data["magnifications"])
    if "methods" in industry_data:
        replacements["{method}"] = random.choice(industry_data["methods"])

    # Additional context-specific replacements
    replacements.setdefault("{line}", f"Line-{random.randint(1, 5)}")
    replacements.setdefault("{proc_id}", f"QP-{random.randint(100, 999)}")
    replacements.setdefault("{scope}", random.choice(["internal", "external", "SOX", "ISO"]))
    replacements.setdefault("{deal}", f"Deal-{random.randint(100, 999)}")
    replacements.setdefault("{jurisdiction}", random.choice(["JP", "US", "UK", "SG", "HK"]))
    replacements.setdefault("{case_id}", f"CASE-{random.randint(10000, 99999)}")
    replacements.setdefault("{patient_id}", f"PT-{random.randint(100000, 999999)}")
    replacements.setdefault("{topic}", random.choice(["genomics", "immunology", "cardiology", "oncology"]))
    replacements.setdefault("{site}", random.choice(["Tokyo", "Osaka", "Nagoya", "Fukuoka"]))
    replacements.setdefault("{track}", f"TRK-{random.randint(1000, 9999)}")
    replacements.setdefault("{segment}", f"SEG-{random.randint(1, 50):02d}")
    replacements.setdefault("{unit}", f"Unit-{random.randint(1, 20):02d}")
    replacements.setdefault("{layer}", random.choice(["elevation", "parcels", "utilities", "zoning"]))
    replacements.setdefault("{district}", random.choice(["North", "South", "East", "West", "Central"]))
    replacements.setdefault("{employee}", f"EMP-{random.randint(1000, 9999)}")
    replacements.setdefault("{course}", random.choice(["safety", "ethics", "IT_security", "leadership"]))
    replacements.setdefault("{scenario}", random.choice(["earthquake", "flood", "fire", "pandemic"]))
    replacements.setdefault("{dept}", random.choice(["public_works", "education", "health", "transport"]))
    replacements.setdefault("{run_id}", f"RUN-{random.randint(1000, 9999)}")
    replacements.setdefault("{experiment}", f"EXP-{random.randint(100, 999)}")
    replacements.setdefault("{study}", f"STUDY-{random.randint(100, 999)}")
    replacements.setdefault("{tile_id}", f"T{random.randint(1000, 9999)}")
    replacements.setdefault("{scenario_id}", f"SC-{random.randint(1000, 9999)}")
    replacements.setdefault("{run}", f"R{random.randint(1, 100):03d}")
    replacements.setdefault("{rfi_num}", f"RFI-{random.randint(100, 999)}")
    replacements.setdefault("{sheet_num}", f"{random.choice(['A', 'S', 'M', 'E', 'P'])}-{random.randint(100, 999)}")
    replacements.setdefault("{phase}", random.choice(["foundation", "structure", "fitout", "commissioning"]))
    replacements.setdefault("{borehole}", f"BH-{random.randint(1, 30):02d}")
    replacements.setdefault("{bg}", random.choice(["white", "lifestyle", "transparent", "studio"]))
    replacements.setdefault("{asset_type}", random.choice(["logo", "icon", "pattern", "typography"]))
    replacements.setdefault("{collection}", random.choice(["classic", "modern", "premium", "casual"]))
    _model_letter = random.choice(["A", "B", "C", "D"])
    _model_num = random.randint(1, 99)
    replacements.setdefault("{model_name}", f"Model-{_model_letter}{_model_num:02d}")
    replacements.setdefault("{doc_num}", f"{random.randint(100000000, 999999999)}")
    replacements.setdefault("{po_num}", f"PO-{random.randint(4500000000, 4599999999)}")
    replacements.setdefault("{delivery_num}", f"DN-{random.randint(8000000000, 8099999999)}")
    replacements.setdefault("{order_num}", f"ORD-{random.randint(1000000, 9999999)}")
    replacements.setdefault("{employee_id}", f"EMP-{random.randint(10000, 99999)}")
    replacements.setdefault("{ecn_num}", f"ECN-{random.randint(1000, 9999)}")
    replacements.setdefault("{so_num}", f"SO-{random.randint(1000000, 9999999)}")
    replacements.setdefault("{batch_num}", f"BATCH-{random.randint(10000, 99999)}")
    replacements.setdefault("{timepoint}", random.choice(["0M", "3M", "6M", "9M", "12M", "24M"]))
    replacements.setdefault("{visit}", f"V{random.randint(1, 12)}")
    replacements.setdefault("{incident_id}", f"INC-{random.randint(10000, 99999)}")
    replacements.setdefault("{deployment}", random.choice(["deploy_alpha", "deploy_bravo", "exercise_01"]))
    replacements.setdefault("{patent_id}", f"PAT-{random.randint(10000, 99999)}")
    replacements.setdefault("{week}", f"W{random.randint(1, 15):02d}")
    replacements.setdefault("{module}", f"M{random.randint(1, 12):02d}")
    replacements.setdefault("{semester}", random.choice(["2024S", "2024A", "2025S"]))
    replacements.setdefault("{degree}", random.choice(["MSc", "PhD", "MD"]))
    replacements.setdefault("{program}", random.choice(["CS", "Engineering", "Medicine", "Business"]))
    replacements.setdefault("{researcher}", f"Researcher-{random.randint(1, 50):02d}")
    replacements.setdefault("{manuscript_id}", f"MS-{random.randint(10000, 99999)}")
    replacements.setdefault("{department}", random.choice(["physics", "chemistry", "biology", "cs"]))
    replacements.setdefault("{sound_name}", random.choice(["impact_01", "whoosh_02", "click_03", "explosion_04"]))
    replacements.setdefault("{action}", random.choice(["run", "attack", "idle", "jump", "death"]))
    replacements.setdefault("{effect}", random.choice(["dissolve", "glow", "distortion", "blur"]))
    replacements.setdefault("{mood}", random.choice(["calm", "battle", "mystery", "victory"]))
    replacements.setdefault("{pose}", random.choice(["action", "portrait", "full_body", "expression"]))
    replacements.setdefault("{chapter}", f"CH{random.randint(1, 20):02d}")
    # Fallback replacements for placeholders that may not be set by industry-specific logic
    replacements.setdefault("{region}", random.choice(["Region-A", "Region-B", "Region-C"]))
    replacements.setdefault("{zone}", random.choice(["Zone-1", "Zone-2", "Zone-3"]))
    replacements.setdefault("{project}", f"PRJ-{random.randint(100, 999)}")
    replacements.setdefault("{scene}", random.choice(["scene_01", "scene_02", "scene_03"]))
    replacements.setdefault("{location}", random.choice(["Location-A", "Location-B", "Location-C"]))
    replacements.setdefault("{method}", random.choice(["method_A", "method_B", "method_C"]))
    replacements.setdefault("{build}", random.choice(["GRCh38", "GRCh37", "T2T"]))
    replacements.setdefault("{equipment}", random.choice(["EQ-01", "EQ-02", "EQ-03"]))
    replacements.setdefault("{area}", random.choice(["Area-1", "Area-2", "Area-3"]))
    replacements.setdefault("{testbench}", random.choice(["tb_top", "tb_core", "tb_io", "tb_mem"]))
    replacements.setdefault("{pattern_set}", random.choice(["scan_full", "bist_mbist", "func_speed", "iddq"]))
    replacements.setdefault("{vehicle_id}", f"VEH-{random.randint(100, 999)}")
    replacements.setdefault("{trial_id}", f"TRIAL-{random.randint(1000, 9999)}")
    replacements.setdefault("{sample}", f"SAMP-{random.randint(100, 999)}")
    replacements.setdefault("{portfolio}", random.choice(["portfolio_A", "portfolio_B", "portfolio_C"]))
    replacements.setdefault("{type}", random.choice(["type_A", "type_B", "type_C"]))
    replacements.setdefault("{regulator}", random.choice(["FSA", "SEC", "FCA"]))
    replacements.setdefault("{agency}", random.choice(["EPA", "METI", "NRC"]))
    replacements.setdefault("{asset}", random.choice(["Bridge-01", "Road-A3", "Building-12", "Park-07"]))

    result = pattern
    for key, value in replacements.items():
        result = result.replace(key, str(value))

    return result


def generate_metadata_record(industry: str, industry_data: dict) -> dict:
    """Generate a single metadata record."""
    template = random.choice(industry_data["file_templates"])
    file_name = generate_file_name(template, industry_data)
    department = random.choice(industry_data["departments"])
    file_size = random.randint(*template["size_range"])
    last_modified = datetime.now() - timedelta(
        days=random.randint(1, 730),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )

    return {
        "file_id": str(uuid.uuid4()),
        "file_name": file_name,
        "file_path": f"/vol1/{department}/{file_name}",
        "file_type": template["type"],
        "file_size": file_size,
        "last_modified": last_modified.isoformat() + "Z",
        "classification": template["classification"],
        "confidence_score": round(random.uniform(0.85, 0.99), 2),
        "department": department,
        "industry": industry,
        "is_deleted": False,
        "enrichment_status": random.choice(["completed", "completed", "completed", "pending"]),
        "content_hash": uuid.uuid4().hex[:32],
        "scan_timestamp": datetime.now().isoformat() + "Z",
    }


def generate_sample_content(industry: str, file_name: str) -> str:
    """Generate sample text content for a file (for text-based files)."""
    content_templates = {
        "manufacturing": (
            f"Document: {file_name}\n"
            f"Department: Engineering\n"
            f"Classification: Technical Document\n\n"
            f"This document contains technical specifications for the component.\n"
            f"Material: Cast Iron FC250 / Stainless Steel SUS304\n"
            f"Tolerance: ±0.05mm\n"
            f"Surface finish: Ra 1.6\n"
            f"Heat treatment: Quenching and tempering\n"
        ),
        "financial": (
            f"Document: {file_name}\n"
            f"Department: Finance & Compliance\n"
            f"Classification: Confidential\n\n"
            f"This document contains financial information subject to regulatory requirements.\n"
            f"Retention period: 7 years\n"
            f"Access: Authorized personnel only\n"
            f"Audit trail: Required\n"
        ),
        "healthcare": (
            f"Document: {file_name}\n"
            f"Department: Clinical Research\n"
            f"Classification: PHI - Protected Health Information\n\n"
            f"This document is subject to HIPAA privacy and security rules.\n"
            f"De-identification required before sharing.\n"
            f"IRB approval: Required for research use\n"
        ),
        "media": (
            f"Document: {file_name}\n"
            f"Department: Production\n"
            f"Classification: Creative Asset\n\n"
            f"Project asset for production use.\n"
            f"License: Internal use only\n"
            f"Resolution: 4K UHD (3840x2160)\n"
            f"Color space: Rec. 2020\n"
        ),
        "public_sector": (
            f"Document: {file_name}\n"
            f"Department: Public Records\n"
            f"Classification: Public Record\n\n"
            f"This document is subject to public records retention requirements.\n"
            f"FOIA: May be subject to disclosure requests\n"
            f"Retention: Per records schedule\n"
        ),
        "energy": (
            f"Document: {file_name}\n"
            f"Department: Operations\n"
            f"Classification: Operational Data\n\n"
            f"This document contains operational data for energy infrastructure.\n"
            f"Safety classification: Critical\n"
            f"Regulatory: Subject to energy commission oversight\n"
        ),
        "legal": (
            f"Document: {file_name}\n"
            f"Department: Legal\n"
            f"Classification: Attorney-Client Privileged\n\n"
            f"This document is protected by attorney-client privilege.\n"
            f"Do not disclose without authorization from General Counsel.\n"
            f"Retention: Per litigation hold requirements\n"
        ),
        "semiconductor": (
            f"Document: {file_name}\n"
            f"Department: IC Design\n"
            f"Classification: Trade Secret\n\n"
            f"This document contains proprietary semiconductor design data.\n"
            f"Export control: Subject to EAR/ITAR restrictions\n"
            f"Access: Design team only\n"
        ),
        "genomics": (
            f"Document: {file_name}\n"
            f"Department: Bioinformatics\n"
            f"Classification: Research Data\n\n"
            f"This document contains genomic sequencing data.\n"
            f"Consent: Broad research consent obtained\n"
            f"De-identification: Required before sharing\n"
            f"Reference genome: GRCh38/hg38\n"
        ),
        "autonomous_driving": (
            f"Document: {file_name}\n"
            f"Department: Perception\n"
            f"Classification: Sensor Data\n\n"
            f"This document contains autonomous driving sensor data.\n"
            f"Privacy: Faces and license plates must be anonymized\n"
            f"Coordinate system: WGS84 / UTM Zone 54N\n"
        ),
        "construction": (
            f"Document: {file_name}\n"
            f"Department: Architecture & Engineering\n"
            f"Classification: Project Document\n\n"
            f"This document is part of the construction project documentation.\n"
            f"BIM Level: LOD 350\n"
            f"Standard: ISO 19650 compliant\n"
        ),
        "retail": (
            f"Document: {file_name}\n"
            f"Department: Creative\n"
            f"Classification: Brand Asset\n\n"
            f"This document is a brand/marketing asset.\n"
            f"Usage rights: Internal and approved channels only\n"
            f"Color profile: sRGB / Adobe RGB\n"
        ),
        "logistics": (
            f"Document: {file_name}\n"
            f"Department: Shipping & Customs\n"
            f"Classification: Trade Document\n\n"
            f"This document is a trade/logistics document.\n"
            f"Customs compliance: Required for cross-border shipments\n"
            f"Retention: 7 years per customs regulations\n"
        ),
        "education": (
            f"Document: {file_name}\n"
            f"Department: Research & Teaching\n"
            f"Classification: Academic\n\n"
            f"This document is an academic/research document.\n"
            f"Open access: Subject to publisher agreement\n"
            f"Data management: Per institutional DMP\n"
        ),
        "insurance": (
            f"Document: {file_name}\n"
            f"Department: Claims & Underwriting\n"
            f"Classification: Policyholder Data\n\n"
            f"This document contains insurance claim/policy information.\n"
            f"Privacy: PII protection required\n"
            f"Retention: Per regulatory requirements\n"
        ),
        "defense": (
            f"Document: {file_name}\n"
            f"Department: Operations\n"
            f"Classification: RESTRICTED\n\n"
            f"This document contains defense-related information.\n"
            f"Handling: Per security classification guidelines\n"
            f"Distribution: Need-to-know basis only\n"
        ),
        "smart_city": (
            f"Document: {file_name}\n"
            f"Department: Urban Planning\n"
            f"Classification: Municipal Data\n\n"
            f"This document contains smart city infrastructure data.\n"
            f"Open data: May be published per open data policy\n"
            f"Privacy: Citizen PII must be anonymized\n"
        ),
        "gaming": (
            f"Document: {file_name}\n"
            f"Department: Game Development\n"
            f"Classification: Creative Asset\n\n"
            f"This document is a game development asset.\n"
            f"Engine: Unreal Engine 5 / Unity\n"
            f"Target platform: Multi-platform\n"
        ),
        "sap_erp": (
            f"Document: {file_name}\n"
            f"Department: Enterprise Operations\n"
            f"Classification: Business Document\n\n"
            f"This document is an SAP ERP business document.\n"
            f"System: SAP S/4HANA\n"
            f"Retention: Per document type retention schedule\n"
            f"Audit: Subject to SOX compliance\n"
        ),
        "life_sciences": (
            f"Document: {file_name}\n"
            f"Department: R&D\n"
            f"Classification: GxP Regulated\n\n"
            f"This document is subject to GxP regulations.\n"
            f"21 CFR Part 11: Electronic records compliance required\n"
            f"Data integrity: ALCOA+ principles apply\n"
        ),
    }
    return content_templates.get(industry, f"Sample content for {file_name}\n")


def print_header(industry: str, count: int):
    """Print generation header."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Sample Data Generator — Iceberg Metadata Catalog Demo       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Industry:    {industry}")
    print(f"  File count:  {count}")
    print(f"  Departments: {', '.join(INDUSTRY_DATA[industry]['departments'])}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Generate realistic sample unstructured file metadata for demos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported industries:
    manufacturing       — CAD files, QC reports, maintenance logs
    financial           — Contracts, audit reports, regulatory filings
    healthcare          — DICOM images, clinical trials, research papers
    media               — Video footage, VFX, audio, graphics
    public_sector       — Permits, GIS maps, public records
    energy              — Well logs, seismic data, pipeline inspections
    legal               — Contracts, NDAs, court filings, privilege logs
    semiconductor       — GDS layouts, timing libs, DRC reports, test vectors
    genomics            — FASTQ files, VCF variants, BAM alignments
    autonomous_driving  — Camera frames, LiDAR scans, HD maps
    construction        — IFC models, drawings, site photos, specifications
    retail              — Product photos, lifestyle images, brand assets
    logistics           — BOLs, customs declarations, delivery proofs
    education           — Papers, theses, datasets, grant proposals
    insurance           — Damage photos, policy docs, claim forms
    defense             — Satellite imagery, mission reports, terrain maps
    smart_city          — GIS maps, sensor data, traffic reports
    gaming              — 3D models, textures, animations, shaders
    sap_erp             — Invoices, purchase orders, production orders
    life_sciences       — Assay results, microscopy images, batch records

Examples:
    python generate-sample-data.py --industry manufacturing --count 100
    python generate-sample-data.py --industry financial --count 50 --output ./data
    python generate-sample-data.py --industry genomics --count 200 --with-content
    python generate-sample-data.py --industry gaming --count 500 --seed 42
        """,
    )
    parser.add_argument(
        "--industry",
        choices=list(INDUSTRY_DATA.keys()),
        required=True,
        help="Industry vertical for sample data generation",
    )
    parser.add_argument(
        "--count", type=int, default=100,
        help="Number of metadata records to generate (default: 100)",
    )
    parser.add_argument(
        "--output", type=str, default="./generated",
        help="Output directory for generated files (default: ./generated)",
    )
    parser.add_argument(
        "--with-content", action="store_true",
        help="Also generate sample text files with industry-appropriate content",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="Upload generated files to FSx S3 Access Point (requires --ap-alias)",
    )
    parser.add_argument(
        "--ap-alias", type=str, default=None,
        help="FSx S3 Access Point alias for upload",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducible generation",
    )
    args = parser.parse_args()

    if args.upload and not args.ap_alias:
        print("  ❌ --upload requires --ap-alias")
        sys.exit(1)

    if args.seed is not None:
        random.seed(args.seed)

    industry_data = INDUSTRY_DATA[args.industry]
    print_header(args.industry, args.count)

    # Generate metadata records
    records = []
    for i in range(args.count):
        record = generate_metadata_record(args.industry, industry_data)
        records.append(record)

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write metadata JSON
    metadata_file = output_dir / f"metadata_{args.industry}.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Generated {len(records)} metadata records")
    print(f"  📄 Metadata file: {metadata_file}")
    print()
    # Generate sample content files if requested
    if args.with_content:
        content_dir = output_dir / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        text_count = 0
        for record in records:
            if record["file_type"] in (".pdf", ".docx", ".xlsx", ".csv", ".txt"):
                content_file = content_dir / f"{record['file_name']}.txt"
                content = generate_sample_content(args.industry, record["file_name"])
                with open(content_file, "w", encoding="utf-8") as f:
                    f.write(content)
                text_count += 1
        print(f"  ✅ Generated {text_count} sample content files")
        print(f"  📁 Content directory: {content_dir}")
        print()

    # Upload to S3 if requested
    if args.upload:
        print("┌──────────────────────────────────────────────────────────────┐")
        print("│  Uploading to FSx S3 Access Point                            │")
        print("└──────────────────────────────────────────────────────────────┘")
        print()
        try:
            import boto3
            s3 = boto3.client("s3")
            uploaded = 0
            for record in records:
                if args.with_content and record["file_type"] in (".pdf", ".docx", ".xlsx", ".csv", ".txt"):
                    content_file = output_dir / "content" / f"{record['file_name']}.txt"
                    if content_file.exists():
                        key = record["file_path"].lstrip("/")
                        s3.upload_file(str(content_file), args.ap_alias, key)
                        uploaded += 1
            print(f"  ✅ Uploaded {uploaded} files to s3://{args.ap_alias}/")
        except ImportError:
            print("  ❌ boto3 not installed. Install with: pip install boto3")
        except Exception as e:
            print(f"  ❌ Upload failed: {e}")
        print()

    # Print summary statistics
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Generation Summary                                          │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    # Classification distribution
    classifications = {}
    total_size = 0
    for r in records:
        cls = r["classification"]
        classifications[cls] = classifications.get(cls, 0) + 1
        total_size += r["file_size"]

    print("  Classification distribution:")
    for cls, count in sorted(classifications.items(), key=lambda x: -x[1]):
        bar = "█" * (count * 30 // args.count)
        print(f"    {cls:<20} {bar} {count}")
    print()

    # File type distribution
    file_types = {}
    for r in records:
        ft = r["file_type"]
        file_types[ft] = file_types.get(ft, 0) + 1

    print("  File type distribution:")
    for ft, count in sorted(file_types.items(), key=lambda x: -x[1]):
        print(f"    {ft:<8} {count:>4} files")
    print()

    # Size summary
    avg_size = total_size / len(records)
    print(f"  Total data volume: {total_size / (1024**3):.1f} GB (simulated)")
    print(f"  Average file size: {avg_size / (1024**2):.1f} MB")
    print()
    print("  Next steps:")
    print(f"    1. Review: cat {metadata_file} | python -m json.tool | head -50")
    print(f"    2. Load into Iceberg: python initial-metadata-scan.py --from-json {metadata_file}")
    if not args.upload:
        print(f"    3. Upload to FSx: python {sys.argv[0]} --industry {args.industry} --upload --ap-alias <alias>")
    print()


if __name__ == "__main__":
    main()
