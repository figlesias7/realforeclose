async function loadDates() {
  const response = await fetch("data/index.json");
  const files = await response.json();

  const dateList = document.getElementById("dateList");
  dateList.innerHTML = "";

  files.forEach(file => {
    const li = document.createElement("li");
    const a = document.createElement("a");

    a.href = "#";
    a.innerText = file.replace(".csv", "");
    a.onclick = () => loadCSV(file);

    li.appendChild(a);
    dateList.appendChild(li);
  });
}

async function loadCSV(file) {
  document.getElementById("selectedDate").innerText = file.replace(".csv", "");

  const response = await fetch(`data/${file}`);
  const text = await response.text();

  const rows = text.trim().split("\n").slice(1);
  const tbody = document.querySelector("#dataTable tbody");
  tbody.innerHTML = "";

  rows.forEach(row => {
    const cols = parseCSVRow(row);
    if (cols.length === 0) return;

    const tr = document.createElement("tr");
    cols.forEach(col => {
      const td = document.createElement("td");
      td.innerText = col;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function parseCSVRow(row) {
  const result = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < row.length; i++) {
    const char = row[i];

    if (char === '"' && row[i + 1] === '"') {
      current += '"';
      i++;
    } else if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += char;
    }
  }

  result.push(current);
  return result;
}

loadDates();