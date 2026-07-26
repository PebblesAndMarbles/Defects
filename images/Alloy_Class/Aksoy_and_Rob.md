July 24 2026

TREY:
\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\images\Alloy_Class\outputs\phase1_combined_report.html

up and running !  thank you both so much for your help and working examples.  I think its a great start but obviously room to give some prior context/expectations/trainings.  End goal is being able to prescribe maybe a few characteristic labels (e.g., large/small, morphology, on/off trench) that I can then test/validate models connected to process parameters.    Misclassifications by the scan/review/classify tools are common, too and worth identifying.  any suggestions, on efficiency?  maybe some references I could review?  
 
Oh and it would seem I don't have an alloy API key beyond the standard demo key.  please let me know if my own key is needed.

ROB:

Hey Trey, these look like a great start. As for suggestions on efficiency, the primary thing that you likely want to focus on is prompt engineer / output structuring to see if you can get away with a less expensive model (GPT-5.4-mini). In general we have found that more detailed and instructive prompts can typically provide good results with less powerful models. For this use case (100-300 images per week) ideally we would be using a cheap model as costs for a frontier model ($15-30/M output) could add up quickly. If you can engineer a good prompt and output structure to get you what you need with a lower-tier model that would be great and make implementation much more straightforward.
 
I will let Aksoy, Doruk answer about the API key specifics and plans going forward.
 



AKSOY:


Hi Trey — this is very promising. Another thought: the vision endpoint supports multi-image processing, so you can pass a list of images. You could try passing both the dark-field and bright-field images at the same time and mention that in the prompt to see how it affects quality.
 
You could also try using an evaluator during the initial ramp-up phase. For example, you can pass the images and the results returned by the agent to another LLM and ask it to evaluate them. I'm curious to see what the accuracy would be on, say, 100 images.
 
For now, we only have one API key, though in a few weeks we'll announce a new authentication method. One thing that would help Alloy users is creating a tool for this and registering it so others can use it in their projects as well. We really want to increase synergies across teams.
 
We're also working on specialized agents that support parametric ML model training, so, for example, we can have object detection or classification computer vision models for downstream processes.
 
Also, Rob is currently compiling a list of all projects to help quantify token usage for the Alloy platform. If you haven't already, could you fill out the template below and send it to alloy@intel.com? We'd really appreciate it.
 
Project Title
	
Org
	
POC(s)
	
Programs affected
	
FTE hours/week saved
	
Velocity
	
Key message
	
Description
	
Implementation status


Example-Agent
	
APTM
	
Rob Jordan
	
EMIB
	
4
	
Data turn around time
3 days -> 1 day
	
Reduced data turnaround time for key programs from 3d -> 1d
	
Custom data agent that digests raw tool data, performs analysis and generates reports. Allows for TO input and direction
	
In-Prod,
local deployment

 	 	 	 	 	 	 	 	 
 
 