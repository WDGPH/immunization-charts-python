#!/bin/bash

INDIR=${1}
FILENAME=${2}
LOGO=${3}
SIGNATURE=${4}
PARAMETERS=${5}
MAP_SCHOOL=${6}

CLIENTIDFILE=${FILENAME}_client_ids.csv
JSONFILE=${FILENAME}.json
OUTFILE=${INDIR}/${FILENAME}_immunization_notice.typ


echo "
// --- CCEYA NOTICE TEMPLATE (TEST VERSION) --- //
// Description: A typst template that dynamically generates 2025 cceya templates for phsd.
// NOTE: All contact details are placeholders for testing purposes only.
// Author: Kassy Raymond
// Date Created: 2025-06-25
// Date Last Updated: 2025-09-16
// ----------------------------------------- //

#import \"conf.typ\"

// General document formatting 
#set text(fill: black)
#set par(justify: false)
#set page(\"us-letter\")

// Formatting links 
#show link: underline

// Font formatting
#set text(
  font: \"FreeSans\",
  size: 10pt
)

// Read current date from yaml file
#let date(contents) = {
  contents.date_today
}

// Read diseases from yaml file 
#let diseases_yaml(contents) = {
    contents.chart_diseases_header
}
  
#let diseases = diseases_yaml(yaml(\"${PARAMETERS}\"))
#let date = date(yaml(\"${PARAMETERS}\"))

// Immunization Notice Section
#let immunization_notice(client, client_id, immunizations_due, date, font_size, school_address, school_phone) = block[

#v(0.2cm)

#conf.header_info_cim(\"${LOGO}\")

#v(0.2cm)

#conf.client_info_tbl_en(equal_split: false, vline: false, client, client_id, font_size)

#v(0.3cm)

// Notice for immunizations
As of *#date* our files show that your child has not received the following immunization(s):  

#conf.client_immunization_list(immunizations_due)

Please review the Immunization Record on page 2 and update your child's record by using one of the following options:

1. By visiting #text(fill:conf.linkcolor)[#link(\"https://www.test-immunization.ca\")]
2. By emailing #text(fill:conf.linkcolor)[#link(\"records@test-immunization.ca\")]
3. By mailing a photocopy of your child’s immunization record to #school_address
4. By Phone: #school_phone

Please update Public Health and your childcare centre every time your child receives a vaccine. By keeping your child's vaccinations up to date, you are not only protecting their health but also the health of other children and staff at the childcare centre.  

*If you are choosing not to immunize your child*, a valid medical exemption or statement of conscience or religious belief must be completed and submitted to Public Health. Links to these forms can be located at #text(fill:conf.wdgteal)[#link(\"https://www.test-immunization.ca/exemptions\")]. Please note this exemption is for childcare only and a new exemption will be required upon enrollment in elementary school.

If there is an outbreak of a vaccine-preventable disease, Public Health may require that children who are not adequately immunized (including those with exemptions) be excluded from the childcare centre until the outbreak is over. 

If you have any questions about your child’s vaccines, please call 555-555-5555 ext. 1234 to speak with a Public Health Nurse.

  Sincerely, 

#conf.signature(\"${SIGNATURE}\", \"Dr. Jane Smith, MPH\", \"Associate Medical Officer of Health\")
  
]

#let vaccine_table_page(client_id) = block[
  
  #v(0.5cm)

  #grid(
  
  columns: (50%,50%), 
  gutter: 5%, 
  [#image(\"${LOGO}\", width: 6cm)],
  [#set align(center + bottom)
    #text(size: 20.5pt, fill: black)[*Immunization Record*]]
  
)

  #v(0.5cm)

  For your reference, the immunization(s) on file with Public Health are as follows:  
  
]

#let end_of_immunization_notice() = [
  #set align(center)
  End of immunization record ]

#let client_ids = csv(\"${CLIENTIDFILE}\", delimiter: \",\", row-type: array)

#for row in client_ids {

  let reset = <__reset>
  let subtotal() = {
  let loc = here()
  let list = query(selector(reset).after(loc))
  if list.len() > 0 { 
    counter(page).at(list.first().location()).first() - 1
  } else {
    counter(page).final().first() 
  }
}

  let page-numbers = context numbering(
  \"1 / 1\",
  ..counter(page).get(),
  subtotal(),
  )

  set page(margin: (top: 1cm, bottom: 2cm, left: 1.75cm, right: 2cm),
  footer: align(center, page-numbers))

  let value = row.at(0) // Access the first (and only) element of the row
  let data = json(\"${JSONFILE}\").at(value)
  let received = data.received

  let school_address = \"Test Health, 123 Placeholder Street, Sample City, ON A1A 1A1\"
  let school_phone = \"555-555-5555 ext. 1234\"

  if \"${MAP_SCHOOL}\" != \"false\" {
    let school = upper(data.school.replace(regex(\"\\s+\"), \"_\"))
    let school_data = json(\"${MAP_SCHOOL}\").at(school)
    school_address = school_data.phu_address
    school_phone = school_data.phu_phone
  }

  let num_rows = received.len()
  
  // get vaccines due, split string into an array of sub strings
  let vaccines_due = data.vaccines_due

  let vaccines_due_array = vaccines_due.split(\", \")

  let section(it) = {
    [#metadata(none)#reset]
    pagebreak(weak: true)
    counter(page).update(1) // Reset page counter for this section
    pagebreak(weak: true)
    immunization_notice(data, row, vaccines_due_array, date, 11pt, school_address, school_phone)
    pagebreak()
    vaccine_table_page(value)
    conf.immunization-table(5, num_rows, received, diseases, 11pt)
    end_of_immunization_notice()
  }

  section([] + page-numbers)

}


" > "${OUTFILE}"