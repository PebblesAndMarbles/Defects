data for BEEP and SMP is being tracked by the pipeline described in \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\PIPELINE_DESIGN.md 

Part of the pipeline involves downloading coordinates for locations of beep or Smp With respect to where they land on the wafer. I have a hypothesis that some small particles in fact our beep fragments .

On some wafers the correlation is obvious, in particular for high flyer wafers where one way forgets a high concentration of say 10 beeps and you may have a couple of small particles in the direct vicinity.

On other wafers this correlation may not be as obvious. Baseline wafers tend to have only a couple of these defects maybe 4 or 5.

The distinction (somewhat arbitrary) between baseline and so called high flyer wafers (>6 particles) is captured in the STATUS Column which is present in the metrics CSV.  

I am envisioning an analysis that allows us to identify specific wafers for which a small particle be more likely to have arisen from a beep.  Effectively we need to perform an analysis comparing spatial distributions of beeps and smps on unique values of WAFER_ID and LAYER (wafers can be scanned on two distinct layers, 8M5CL or 8M6CL) across the entire dataset described by pipeline_design.md

Could you please review the design documentation as well as the source CSV and propose an alalysis?

One downstream component of this project could also be to generate html reports of suspicious highflier & baseline wafers using an approach similar to \\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\rollups\CENTER_DEFECT_REPORT.py showing both wafermaps, and defect images.