# Student Overdue Vaccine List Preparation Process

The vaccine notification generation process requires lists of students who are overdue for vaccines. There are two options for list preparation:

- Non-ISPA and ISPA data
- ISPA data only

Non-ISPA (e.g., Hepatitis B and HPV) and ISPA lists require overdue data from both Panorama Forecast Query (FQ) and PEAR reports. These reports should be given to WDGPH and we will merge them accordingly.

**If generating lists for ISPA vaccines only, only the Forecast Query (FQ) reports are required.**


## Required Reports

1. Panorama Forecast Query
    - ISPA vaccines only
2. PEAR – Overdue by Disease
    - Elementary: ISPA vaccines only
    - Secondary: ISPA and non-ISPA vaccines; includes students out of ISPA-requirement age range
    - Recommendations:
        - Set Birthdate Range End and Overdue Date Time to 11:59 PM
        - Use multiple reports (e.g., by birth year, Varicella status, non-ISPA vaccines) for efficient performance
3. PEAR – Philosophical Exemptions
    - Used to exclude secondary students with active exemptions who are only overdue for non-ISPA vaccines or are out of ISPA-requirement age range
    - Note the that the value “, “ in the Repeater field means the group of ISPA vaccines as been selected for exemption

## PEAR Missing Data from Special Characters

- PEAR reports may have blank fields for Overdue Disease, Agent, or Imms Given if student names/addresses contain special characters.
- Workaround:
  - Run PEAR without name and address fields to recover missing data
  - Optionally, clean special characters in Panorama to prevent future issues
