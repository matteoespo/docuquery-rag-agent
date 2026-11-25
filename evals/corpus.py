"""Synthetic eval corpus: three manuals for fictional products.

The products don't exist, so a correct answer can only come from the documents
(not from the model's general knowledge). Zorvex Q7 and Q9 are deliberately
similar with different values, to test that retrieval picks the right manual.
"""

from pathlib import Path

import pymupdf

# file name -> list of pages; each page is a list of lines.
MANUALS: dict[str, list[list[str]]] = {
    "zorvex_q7_manual.pdf": [
        ["Zorvex Q7 Hydraulic Pump - Technical Manual", "",
         "Section 1: Overview",
         "The Zorvex Q7 is a compact hydraulic pump for agricultural machinery.",
         "It delivers a maximum flow rate of 42 litres per minute."],
        ["Section 2: Electrical Specifications",
         "Input voltage: 36 V DC.",
         "Maximum current draw: 14 A.",
         "The pump must be grounded via terminal G3."],
        ["Section 3: Maintenance",
         "Replace the Zorvex Q7 filter cartridge (part ZF-220) every 400 operating hours.",
         "Change the hydraulic oil every 1200 operating hours.",
         "Use only HV-46 hydraulic oil."],
        ["Section 4: Troubleshooting - Error Codes",
         "E1 - Low oil level - Top up with HV-46 oil.",
         "E2 - Motor overheating - Let the pump cool down for 30 minutes.",
         "E3 - Overpressure - Inspect relief valve RV-2.",
         "E4 - Sensor fault - Check the pressure sensor cable on connector J7."],
    ],
    "zorvex_q9_manual.pdf": [
        ["Zorvex Q9 Hydraulic Pump - Technical Manual", "",
         "Section 1: Overview",
         "The Zorvex Q9 is a heavy-duty hydraulic pump for construction machinery.",
         "It delivers a maximum flow rate of 75 litres per minute."],
        ["Section 2: Electrical Specifications",
         "Input voltage: 48 V DC.",
         "Maximum current draw: 22 A.",
         "The pump must be grounded via terminal G5."],
        ["Section 3: Maintenance",
         "Replace the Zorvex Q9 filter cartridge (part ZF-310) every 600 operating hours.",
         "Change the hydraulic oil every 1500 operating hours.",
         "Use only HV-68 hydraulic oil."],
    ],
    "kestrel_kx200_manual.pdf": [
        ["Kestrel KX-200 Conveyor Controller - User Manual", "",
         "Section 1: Overview",
         "The Kestrel KX-200 controls belt conveyors with up to four motors.",
         "Operating temperature range: -10 to 50 degrees Celsius."],
        ["Section 2: Configuration",
         "Maximum belt speed: 2.4 metres per second.",
         "The default acceleration ramp is 3 seconds.",
         "The emergency stop must be wired as a normally closed (NC) contact on terminal X5."],
        ["Section 3: Firmware Update",
         "1. Copy the firmware file KX200.bin to a FAT32 USB drive.",
         "2. Insert the drive into the service port.",
         "3. Hold the MODE button for 10 seconds until the status LED blinks green.",
         "4. Do not power off the controller until the LED stays solid green."],
    ],
}


def build_synthetic_corpus(dest: Path) -> list[str]:
    """Write the manuals as PDFs into ``dest`` and return their paths."""
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, pages in MANUALS.items():
        doc = pymupdf.open()
        for lines in pages:
            doc.new_page().insert_text((72, 72), "\n".join(lines), fontsize=11)
        path = dest / name
        doc.save(str(path))
        doc.close()
        paths.append(str(path))
    return paths
