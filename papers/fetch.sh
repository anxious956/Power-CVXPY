#!/usr/bin/env bash
# Download the open-access PDFs listed in papers/README.md into this folder.
#   bash papers/fetch.sh
set -e
cd "$(dirname "$0")"
dl(){ curl -sL -o "$2" "$1" && echo "OK   $2" || echo "FAIL $2"; }

# SEL posts its conference papers and technical reports free, but the site blocks
# non-browser user agents, so a plain curl usually returns an HTML error page rather
# than the PDF. We send a browser UA and then check that what came back really is a
# PDF; if it is not, the file is removed and you are told to open the URL by hand.
sel(){
  curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -o "$2" "https://selinc.com/api/download/$1/" || true
  if [ -s "$2" ] && head -c 4 "$2" | grep -q '%PDF'; then
    echo "OK   $2"
  else
    rm -f "$2"
    echo "FAIL $2  -> open https://selinc.com/api/download/$1/ in a browser and save it as this name"
  fi
}

# A. Taylor's line
dl https://arxiv.org/pdf/2209.06760 "Pirani_Taylor_2022_Optimal_Active_Fault_Detection_Inverter_Grids.pdf"
dl https://arxiv.org/pdf/2311.10880 "Taylor_2023_Auxiliary_Signal_Based_Distance_Protection_IBR.pdf"
dl https://arxiv.org/pdf/2510.04379 "Taylor_2025_Geometry_of_Distance_Protection.pdf"
dl https://arxiv.org/pdf/2604.16668 "Taylor_2026_Distance_Characteristics_Incremental_Quantities.pdf"
dl https://arxiv.org/pdf/2608.19678 "Taylor_2026_Reachability_Time_Domain_Distance_Protection.pdf"
# B. The problem statement, from people who build relays
dl https://www.osti.gov/servlets/purl/2429968/ "Sandia_2024_Protection_100pct_Inverter_Dominated_Gap_Analysis.pdf"
dl https://arxiv.org/pdf/2505.04177 "2025_Impact_of_Grid_Forming_Inverters_on_Protective_Relays.pdf"
dl https://arxiv.org/pdf/2603.27816 "2026_Impact_of_IBR_on_Protection_of_the_Electrical_Grid.pdf"
dl https://arxiv.org/pdf/2504.21592 "2025_Protection_Interoperable_Fault_Ride_Through_Control_GFM.pdf"

# C. Closest related work
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

# H. Practitioner references for settings and instrument transformers (SEL, free)
sel 133569 "2021_SEL_Settings_Considerations_Distance_Elements.pdf"
sel 134587 "2022_SEL_Distance_Elements_Near_Unconventional_Sources.pdf"
sel 138266 "2023_SEL_Security_Criterion_Zone1_High_SIR_CCVT.pdf"
sel 2398   "1996_SEL_CVT_Transient_Overreach_Distance_Relaying.pdf"
sel 99416  "2012_SEL_CVT_Transients_Revisited.pdf"
sel 141627 "2026_SEL_From_Complexity_to_Consistency_IBR_Fault_Response.pdf"

echo
echo "Not publicly downloadable - these two are held in papers/ but this script cannot fetch them."
echo "Both are IEEE, paywalled; get them through the NJIT library (or ask Prof. Taylor):"
echo "  - Taylor & Dominguez-Garcia, 'Active Fault Detection in Static Systems',"
echo "      IEEE Trans. Automatic Control 70(8):5523-5529, 2025."
echo "      DOI 10.1109/TAC.2024.3510612  ->  library/Taylor_2025_Active_Fault_Detection_Static_Systems.pdf"
echo "  - Baeckeland, Yang & Seo, 'A unified model of current-limiting grid-forming inverters"
echo "      for large-signal analysis', IEEE Trans. Power Systems 41(1):198-213, 2026."
echo "      DOI 10.1109/TPWRS.2025.3587224  ->  library/Baeckeland_2026_Unified_Model_Current_Limiting_GFM_Inverters.pdf"

echo
# K. Direction and fault type at inverter buses (added 29 Sep 2026). The first two are over the repo's
# 5 MB limit and are listed in .gitignore; the rest of section K's held files are committed.
dl https://pure.tudelft.nl/ws/portalfiles/portal/146470145/A_Control_Method_for_Converter_Interfaced_Sources_to_Improve_Operation_of_Directional_Protection_Elements.pdf "2023_Yang_Control_Method_Directional_Protection_Elements.pdf"
dl https://www.osti.gov/servlets/purl/1595917 "Sandia_2020_IBR_Negative_Sequence_Injection_SAND2020-0265.pdf"
dl https://www.pes-psrc.org/kb/report/109.pdf "2020_PES_TR81_Protection_Challenges_IBR_Transmission.pdf"
sel 137350 "2022_SEL_Line_Current_Differential_IBR.pdf"
dl https://www.ipstconf.org/papers/Proc_IPST2023/23IPST020.pdf "2023_IEEE2800_Benefits_Transmission_Line_Protection_IPST.pdf"
dl https://www.osti.gov/servlets/purl/2377006 "2024_PNNL_IBR_Negative_Sequence_Current_Review.pdf"
dl https://web.mit.edu/braatzgroup/input_design_for_guaranteed_fault_diagnosis_using_zonotopes.pdf "2014_Scott_Input_Design_Guaranteed_Fault_Diagnosis_Zonotopes.pdf"
dl https://web.mit.edu/braatzgroup/Raimondo_Automatica_2016.pdf "2016_Raimondo_Closed_Loop_Input_Design_Guaranteed_Fault_Diagnosis.pdf"
dl https://par.nsf.gov/servlets/purl/10283128 "2021_Directionality_SVM_Synthetic_Harmonic_Injection.pdf"
dl "https://esic.wsu.edu/documents/2023/10/western-protective-relay-conference-2021-transmission-line-protection-for-systems-with-inverter-based-resources.pdf/" "2021_SEL_Line_Protection_IBR_Solutions_WPRC.pdf"

echo "Still missing, see papers/README.md section F:"
echo "  - Campbell & Nikoukhah, 'Auxiliary Signal Design for Failure Detection', Princeton UP 2004"
echo "  - Baeckeland et al. 2022, distance protection of grids dominated by grid-forming inverters"
echo "  - IEEE Std 2800-2022"
