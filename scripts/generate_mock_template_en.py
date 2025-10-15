import sys
from pathlib import Path

# Inputs
indir = Path(sys.argv[1])  
filename = sys.argv[2]
logo = sys.argv[3]
signature = sys.argv[4]
parameters = sys.argv[5]

clientidfile = f'{filename}_client_ids.csv'
jsonfile = f'{filename}.json'
outfile = f'{filename}_immunization_notice.typ'

# --- Typst Template Content ---
template = f"""// --- CCEYA NOTICE TEMPLATE (TEST VERSION) --- //
// Description: A typst template that dynamically generates 2025 cceya templates for phsd.
// NOTE: All contact details are placeholders for testing purposes only.
// Author: Kassy Raymond
// Date Created: 2025-06-25
// Date Last Updated: 2025-09-16
// ----------------------------------------- //

#import "conf.typ"

#set text(fill: black)
#set par(justify: false)
#set page("us-letter")

#show link: underline

#set text(
  font: "FreeSans",
  size: 10pt
)

#let date(contents) = {{
  contents.date_today
}}

#let diseases_yaml(contents) = {{
  contents.chart_diseases_header
}}
  
#let diseases = diseases_yaml(yaml("{parameters}"))
#let date = date(yaml("{parameters}"))

#let immunization_notice(client, client_id, immunizations_due, date, font_size) = block[
#v(0.2cm)
#conf.header_info_cim("{logo}")
#v(0.2cm)
#conf.client_info_tbl_en(equal_split: false, vline: false, client, client_id, font_size)
#v(0.3cm)

As of *#date* our files show that your child has not received the following immunization(s):  

#conf.client_immunization_list(immunizations_due)

Please review the Immunization Record on page 2 and update your child's record by using one of the following options:

1. By visiting #text(fill:conf.linkcolor)[#link("https://www.test-immunization.ca")]
2. By emailing #text(fill:conf.linkcolor)[#link("records@test-immunization.ca")]
3. By mailing a photocopy of your child’s immunization record to Test Health, 123 Placeholder Street, Sample City, ON A1A 1A1
4. By Phone: 555-555-5555 ext. 1234

Please update Public Health and your childcare centre every time your child receives a vaccine. 

*If you are choosing not to immunize your child*, a valid medical exemption or statement of conscience or religious belief must be submitted. 

If there is an outbreak, children who are not adequately immunized may be excluded.

If you have any questions, please call 555-555-5555 ext. 1234.

Sincerely,
#conf.signature("{signature}", "Dr. Jane Smith, MPH", "Associate Medical Officer of Health")
]

#let vaccine_table_page(client_id) = block[
#v(0.5cm)
#grid(columns: (50%,50%), gutter: 5%, [#image("{logo}", width: 6cm)], [#set align(center + bottom) #text(size: 20.5pt, fill: black)[*Immunization Record*]])
#v(0.5cm)
For your reference, the immunization(s) on file with Public Health are as follows:
]

#let end_of_immunization_notice() = [#set align(center) End of immunization record]

#let client_ids = csv("{clientidfile}", delimiter: ",", row-type: array)

#for row in client_ids {{
  let reset = <__reset>
  let subtotal() = {{
    let loc = here()
    let list = query(selector(reset).after(loc))
    if list.len() > 0 {{
      counter(page).at(list.first().location()).first() - 1
    }} else {{
      counter(page).final().first() 
    }}
  }}

  let page-numbers = context numbering("1 / 1", ..counter(page).get(), subtotal())

  set page(margin: (top: 1cm, bottom: 2cm, left: 1.75cm, right: 2cm),
           footer: align(center, page-numbers))

  let value = row.at(0)
  let data = json("{jsonfile}").at(value)
  let received = data.received
  let num_rows = received.len()
  let vaccines_due = data.vaccines_due
  let vaccines_due_array = vaccines_due.split(", ")

  let section(it) = {{
    [#metadata(none)#reset]
    pagebreak(weak: true)
    counter(page).update(1)
    pagebreak(weak: true)
    immunization_notice(data, row, vaccines_due_array, date, 11pt)
    pagebreak()
    vaccine_table_page(value)
    conf.immunization-table(5, num_rows, received, diseases, 11pt)
    end_of_immunization_notice()
  }}
  section([] + page-numbers)
}}
"""