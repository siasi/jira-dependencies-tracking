After practcing with this script for a while I am getting clarity of the benefit they can bring.
I have following consideration:

1. This is a toolkit for engineering managers. It started as a single script to extract data from Jira and is now becoming a bunch of scripts that can work together to generate some reports. We should find a more consisten name for the repo. 
2. The idea is to follow a simple process using this toolking:
    1. extract data and store locally (the jira_extract.py script)
    2. process those data
        1. planning use case - you want to validate planning rediness on new initiatives. You address data quality issues until the initiative is planned or rejected. You can also anticipate those initiatives that won't complete during the next quarter becasue contributing teams can't commit or have low confidence in delivery (validate_initiative_status.py)
        2. workload analysis - you consider all the planned and in progress initiatives and track how the workload distribute across the teams (analyse_workload.py)
        3. delivery use case - you can extract information for workin progress initiatives and surface blockers, ETA and confidence in meeting the ETA (not implemented yet). 
3. Currently the jira_extract.py has flexibility to filter data through options (quarter, status, jql). However there are 2 real usage (see the list). 
    1. You want to extract all the initiatives proposed for the next quarter. You use this for the planning use case.
    2. You want to extact all the initiatives in progress or proposed. You use this for the workload analysis.
4. I think the extarct script should be used to extract always all the data of the initiatives and then the filter should be implemented in the specific scripts (i.e. the validate_initiative_status.py should only consider the planned initiatives for the quarter, while the analyse_workload.py should include all the in progress initiatives). 
5. Currently the names of the script have no consistency. Is there a better way of naming them or a better facade?
6. The repository layout is confusing. all configuration files (there are multiple) should stay all in a conf directory and only the main scripts should stay in the main folder, shile the others should go in a lib folder or similar.
7. Some script have --md option that create a markdown file. Some others have the same option that change the output of the script, without creating the file. I think this should be consistent. 
8. Some script have links for Jira Initiatives/Epics keys in the output. I am not sure this is true for all the reports. 
9. Some scripts use templates, some others not. We should use templates consistently. 
10. This is now implemented as bunch of scripts that are used by a central autohority to validate Jira status and extract valuable information for planning, workload and delivery. However, while this is the use case we started from, I would like to explore evolving the toolkit to be used directly by engineering managers. Maybe adding a --me option or similar to the scripts, so that they return only info relevant for the manager can be a way of exploring this idea
