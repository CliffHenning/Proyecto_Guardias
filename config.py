TRAMOS_HORARIOS = {
	1: "8:45-9:45",
	2: "9:35-10:25",
	3: "10:25-11:15",
	4: "11:45-12:35",
	5: "12:35-13:25",
	6: "13:25-14:15",
	7: "15:40-16:30",
	8: "16:30-17:20",
	9: "17:20-18:10",
	10: "18:10-19:00",
	11: "19:20-20:10",
}


def describir_hora(hora):
	tramo = TRAMOS_HORARIOS.get(hora)
	if tramo is None:
		return str(hora)
	return f"{hora} ({tramo})"


def describir_horas(horas):
	return ", ".join(describir_hora(hora) for hora in sorted(horas))
