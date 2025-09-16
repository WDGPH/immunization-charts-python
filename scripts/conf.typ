#let vax = ("⬤")

// Custom colours
#let wdgteal = rgb(0, 85, 104)
#let darkred = rgb(153, 0, 0)
#let darkblue = rgb(0, 83, 104)
#let linkcolor = rgb(0, 0, 238)

#let header_info_cim(
  logo
) = {
  grid(
  
    columns: (50%,50%), 
    gutter: 5%, 
    [#image(logo, width: 6cm)],
    [#set align(center + bottom)
      #text(size: 18pt, fill: black)[*Request for your child's immunization record*]]
    
  )
}

#let client_info_tbl_en(
  equal_split: true,
  vline: true, 
  client_data,
  client_id,
  font_size
) = {
  // Define column widths based on equal_split
  let columns = if equal_split {
    (0.5fr, 0.5fr)
  } else {
    (0.4fr, 0.6fr)
  }

  let vline_stroke = if vline { 1pt + black } else { none }

  // Content for the first column
  let col1_content = align(left)[
    To Parent/Guardian of: #linebreak()
    *#client_data.name* #linebreak()
    #v(0.02cm)
    *#client_data.address* #linebreak()
    *#client_data.city*, *Ontario* *#client_data.postal_code*
  ]

  // Content for the second column
  let col2_content = align(left)[
    Client ID: #smallcaps[*#client_id.at(0)*] #v(0.02cm)
    Date of Birth: *#client_data.date_of_birth* #v(0.02cm)
    Childcare Centre: #smallcaps[*#client_data.school*]
  ]

  // Central alignment for the entire table
  align(center)[
    #table(
      columns: columns,
      inset: font_size,
      col1_content,
      table.vline(stroke: vline_stroke),
      col2_content,
    )
  ]
}

#let client_immunization_list(
  immunizations_due
) = {

  let list-content = {
    for vaccine in immunizations_due [
      - *#vaccine*
    ]
  }
  
  let num_elements = immunizations_due.len()
  set list(indent: 0.8cm)
  if num_elements > 4 {   
    align(center, block(
      height: 60pt,
      width: 545pt,
      columns(3)[ 
      #align(left + top)[
      #for vaccine in immunizations_due [
        - *#vaccine*
      ]
    ]
    ]
  ))
  } else {
    [#list-content]
  }
  
}

#let signature(
  signature, 
  name, 
  title
) = {

  image(signature, width: 3cm)
  
  text(name)
  linebreak()
  text(title)
  
}

#let immunization-table(
  min_rows, 
  num_rows, 
  data, 
  diseases,
  font_size,
  at_age_col: true
) = {

  let num_padded = min_rows - num_rows
  let table_rows = ()
  let empty_rows_content = ()
  let dynamic_headers = ()

  if num_rows > 0 {
      for record in data {
    // Start row with Date Given and At Age
    let row_cells = (
      record.date_given,
    )

    // Populate disease columns with #vax or empty
    for disease_name in diseases {

      let cell_content = ""
      for record_disease in record.diseases {
        if record_disease == disease_name { 
          cell_content = vax
          // Found a match, no need to check other diseases for this cell
          break 
        }
      }
      row_cells.push(cell_content)
    }
        // Add the Vaccine(s) column content
    let vaccine_content = if type(record.vaccine) == array {
      record.vaccine.join(", ") 
    } else {
      record.vaccine
    }
    row_cells.push(vaccine_content)

    table_rows.push(row_cells)
  }

  }

  if num_padded > 0 {
     for _ in range(num_padded) {
  table_rows.push(("", "", "", "", "", "", "", "", "", "", "", "", "", ""," "))
  } 
  }
  
  dynamic_headers.push([#align(bottom + left)[#text(size: font_size)[Date Given]]])

  for disease in diseases {
    dynamic_headers.push([#align(bottom)[#text(size: font_size)[#rotate(-90deg, reflow: true)[#disease]]]])
  }

  dynamic_headers.push([#align(bottom + left)[#text(size: font_size)[Vaccine(s)]]])
  
  // --- Create the table ---
  align(center)[
    #table(
        columns: (67pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 16pt, 236pt),
        table.header(
          ..dynamic_headers
        ),
      stroke: 1pt,
      inset: 5pt,
      align: (
        left,
        center,
        center,
        center,
        center,
        center,
        center,
        center,
        center,
        center,
        center,
        center,
        center,
        left
      ), 
      ..table_rows.flatten(), 
      table.cell(stroke:none, align: right, colspan: 15)[#text(size: 1em)[\*\indicates unspecified vaccine agent]]
    )
  ]

}