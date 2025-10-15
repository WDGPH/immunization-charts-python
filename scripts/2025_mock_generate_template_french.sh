#!/bin/bash

INDIR=${1}
FILENAME=${2}
LOGO=${3}
SIGNATURE=${4}
PARAMETERS=${5}

#v(0.2cm)

#conf.header_info_cim("${LOGO}")

#v(0.2cm)

#conf.client_info_tbl_fr(equal_split: false, vline: false, client, font_size)4}
PARAMETERS=${5}

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
#let immunization_notice(data, value, immunizations_due, date, font_size) = block[

#v(0.2cm)

#conf.header_info_cim(\"${LOGO}\")

#v(0.2cm)

#align(center)[
#table(
  columns: (0.5fr, 0.5fr),
  inset: 11pt,
  [#align(left)[
    Aux parents/tuteurs de: \
    #linebreak()
*#data.name* \
#linebreak()

*#data.address*  \
#linebreak()
*#data.city*, *Ontario* *#data.postal_code*  ]],
table.vline(stroke: {1pt + black} ),
  [#align(left)[
    ID du client: #smallcaps[*#value*]\
    #v(0.02cm)
    Date de naissance: *#data.date_of_birth*\
    #v(0.02cm)
    Centre de garde d'enfants: #smallcaps[*#data.school*]
  ]],
)
]

#v(0.3cm)

// Notice for immunizations
En date du *#date*, nos dossiers indiquent que votre enfant n'a pas reçu les immunisations suivantes :  

#conf.client_immunization_list(immunizations_due)

Veuillez examiner le dossier d'immunisation à la page 2 et mettre à jour le dossier de votre enfant en utilisant l'une des options suivantes :

1. En visitant #text(fill:conf.linkcolor)[#link(\"https://www.test-immunization.ca\")[https://www.test-immunization.ca]]
2. En envoyant un courriel à #text(fill:conf.linkcolor)[#link(\"mailto:records@test-immunization.ca\")[#text(\"records@test-immunization.ca\")]]
3. En envoyant par la poste une photocopie du dossier d'immunisation de votre enfant à Test Health, 123 Placeholder Street, Sample City, ON A1A 1A1
4. Par téléphone : 555-555-5555 poste 1234

Veuillez informer la Santé publique et votre centre de garde d'enfants chaque fois que votre enfant reçoit un vaccin. En gardant les vaccinations de votre enfant à jour, vous protégez non seulement sa santé, mais aussi la santé des autres enfants et du personnel du centre de garde d'enfants.  
#grid(
  columns: (1fr, auto),
  gutter: 10pt,
  [*Si vous choisissez de ne pas immuniser votre enfant*, une exemption médicale valide ou une déclaration de conscience ou de croyance religieuse doit être remplie et soumise à la Santé publique. Les liens vers ces formulaires se trouvent à #text(fill:conf.wdgteal)[#link(\"https://www.test-immunization.ca/exemptions\")[https://www.test-immunization.ca/exemptions]]. Veuillez noter que cette exemption est uniquement pour la garde d'enfants et qu'une nouvelle exemption sera requise lors de l'inscription à l'école primaire.],
  [#if \"qr_code\" in data [
    #image(data.qr_code, width: 2cm)
  ]]
)
En cas d'éclosion d'une maladie évitable par la vaccination, la Santé publique peut exiger que les enfants qui ne sont pas adéquatement immunisés (y compris ceux avec exemptions) soient exclus du centre de garde d'enfants jusqu'à la fin de l'éclosion. 

Si vous avez des questions sur les vaccins de votre enfant, veuillez appeler le 555-555-5555 poste 1234 pour parler à une infirmière de la Santé publique.
Sincères salutations, 
#v(0.2cm)
#conf.signature(\"${SIGNATURE}\", \"Dr. Jane Smith, MPH\", \"Médecin hygiéniste adjoint\")

  
]

#let vaccine_table_page(client_id) = block[
  
  #v(0.5cm)

  #grid(
  
  columns: (50%,50%), 
  gutter: 5%, 
  [#image(\"${LOGO}\", width: 6cm)],
  [#set align(center + bottom)
    #text(size: 20.5pt, fill: black)[*Dossier d'immunisation*]]
  
)

  #v(0.5cm)

  Pour votre référence, les immunisations enregistrées auprès de la Santé publique sont les suivantes :  
  
]

#let end_of_immunization_notice() = [
  #set align(center)
  Fin du dossier d'immunisation ]

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

  let num_rows = received.len()
  
  // get vaccines due, split string into an array of sub strings
  let vaccines_due = data.vaccines_due

  let vaccines_due_array = vaccines_due.split(\", \")

  let section(it) = {
    [#metadata(none)#reset]
    pagebreak(weak: true)
    counter(page).update(1) // Reset page counter for this section
    pagebreak(weak: true)
    immunization_notice(data, value, vaccines_due_array, date, 11pt)
    pagebreak()
    vaccine_table_page(value)
    conf.immunization-table(5, num_rows, received, diseases, 11pt)
    end_of_immunization_notice()
  }

  section([] + page-numbers)

}


" > "${OUTFILE}"
