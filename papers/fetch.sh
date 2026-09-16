#!/usr/bin/env bash
# Download the open-access (arXiv) PDFs listed in papers/README.md into this folder.
# PDFs are not committed to the repo; run this once after cloning.
#   bash papers/fetch.sh
set -e
cd "$(dirname "$0")"
dl(){ curl -sL -o "$2" "$1" && echo "OK   $2" || echo "FAIL $2"; }

# A. Taylor's line
dl https://arxiv.org/pdf/2209.06760 "Pirani_Taylor_2022_Optimal_Active_Fault_Detection_Inverter_Grids.pdf"
dl https://arxiv.org/pdf/2510.04379 "Taylor_2025_Geometry_of_Distance_Protection.pdf"
dl https://arxiv.org/pdf/2604.16668 "Taylor_2026_Distance_Characteristics_Incremental_Quantities.pdf"
dl https://arxiv.org/pdf/2608.19678 "Taylor_2026_Reachability_Time_Domain_Distance_Protection.pdf"
# B. Closest related work
dl https://arxiv.org/pdf/2205.02962 "2022_Incremental_Negative_Sequence_Admittance_Fault_Detection_Inverter_Microgrids.pdf"
dl https://arxiv.org/pdf/2604.10129 "2026_Incremental_Quantity_Distance_Protection_Grid_Forming_Inverters.pdf"
dl https://arxiv.org/pdf/2405.07310 "2024_ML_Protection_100pct_Inverter_Microgrids.pdf"
dl https://arxiv.org/pdf/2401.10959 "2024_ML_Classification_Converter_Control_Mode.pdf"
# C. Datasets and benchmarks
dl https://arxiv.org/pdf/2606.24298 "2026_PROTECT90_Fault_Dataset.pdf"
dl https://arxiv.org/pdf/2608.19777 "2026_Simulation_Dataset_Faults_Events_ML_Power_Systems.pdf"
dl https://arxiv.org/pdf/2510.00831 "2025_Benchmarking_ML_Fault_Classification_Localization_Protection.pdf"
dl https://arxiv.org/pdf/2605.17256 "2026_Latency_Aware_DL_Benchmark_Inverter_Dominated_Grids.pdf"
dl https://arxiv.org/pdf/2507.10011 "2025_Survey_AI_Fault_Detection_Classification_Location.pdf"

echo
echo "Not open access (get via NJIT library): Taylor & Dominguez-Garcia, 'Active Fault Detection in Static Systems', IEEE TAC 70(8), 2025."
