"""Single source of truth for the LED chaser: parts, footprints, nets, schematic placement."""
GND, VCC = "GND", "VCC"

# ref: (lib_id, value, footprint, (x, y), rot, mirror_y, {pin: net})
PARTS = {
    # ---- power input ----
    "J1": ("Connector:Screw_Terminal_01x02", "VIN 5-12V", "TerminalBlock:TerminalBlock_bornier-2_P5.08mm",
           (25.4, 45.72), 0, True, {"1": "VIN", "2": GND}),
    "D11": ("Device:D_Schottky", "1N5817", "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
            (48.26, 45.72), 180, False, {"2": "VIN", "1": VCC}),
    "C3": ("Device:C_Polarized", "100uF", "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
           (68.58, 48.26), 0, False, {"1": VCC, "2": GND}),
    "C4": ("Device:C", "100nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
           (83.82, 48.26), 0, False, {"1": VCC, "2": GND}),
    "C5": ("Device:C", "100nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
           (99.06, 48.26), 0, False, {"1": VCC, "2": GND}),
    # ---- 555 astable clock ----
    "U1": ("Timer:NE555P", "NE555P", "Package_DIP:DIP-8_W7.62mm",
           (53.34, 113.03), 0, False,
           {"1": GND, "2": "THR", "3": "CLK", "4": VCC, "5": "CV", "6": "THR", "7": "DIS", "8": VCC}),
    "R1": ("Device:R", "1k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           (91.44, 96.52), 0, False, {"1": VCC, "2": "DIS"}),
    "R2": ("Device:R", "10k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           (91.44, 111.76), 0, False, {"1": "DIS", "2": "POT"}),
    "RV1": ("Device:R_Potentiometer", "100k SPEED", "Potentiometer_THT:Potentiometer_Bourns_3386P_Vertical",
            (91.44, 127.0), 0, False, {"1": "POT", "2": "THR", "3": "THR"}),
    "C1": ("Device:C_Polarized", "4.7uF", "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm",
           (91.44, 142.24), 0, False, {"1": "THR", "2": GND}),
    "C2": ("Device:C", "10nF", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
           (30.48, 139.7), 0, False, {"1": "CV", "2": GND}),
    "D12": ("Device:LED", "Green CLK", "LED_THT:LED_D3.0mm",
            (114.3, 96.52), 90, False, {"2": "CLK", "1": "CLKLED"}),
    "R4": ("Device:R", "1k", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           (114.3, 111.76), 0, False, {"1": "CLKLED", "2": GND}),
    # ---- CD4017 decade counter ----
    "U2": ("4xxx:4017", "CD4017B", "Package_DIP:DIP-16_W7.62mm",
           (167.64, 111.76), 0, False,
           {"14": "CLK", "13": GND, "15": GND, "16": VCC, "8": GND,
            "3": "Q0", "2": "Q1", "4": "Q2", "7": "Q3", "10": "Q4",
            "1": "Q5", "5": "Q6", "6": "Q7", "9": "Q8", "11": "Q9", "12": None}),
    "R3": ("Device:R", "470", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
           (256.54, 106.68), 0, False, {"1": "LEDK", "2": GND}),
}
for i in range(10):
    PARTS[f"D{i+1}"] = ("Device:LED", "Red", "LED_THT:LED_D5.0mm",
                        (231.14, 60.96 + i * 10.16), 180, False, {"2": f"Q{i}", "1": "LEDK"})
for i in range(4):
    PARTS[f"H{i+1}"] = ("Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3",
                        (25.4 + i * 10.16, 185.42), 0, False, {})

POWER_NETS = {GND, VCC}

# direct pin-to-pin wires (instead of stub + label); optional net label placed on the wire
WIRES = [("R1", "2", "R2", "1", "DIS"), ("R2", "2", "RV1", "1", "POT"),
         ("RV1", "3", "C1", "1", "THR"), ("D12", "1", "R4", "1", "CLKLED")]
HIDE_VALUE = {f"D{i}" for i in range(1, 11)}
