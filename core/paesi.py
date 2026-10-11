"""core/paesi.py — elenco delle nazionalità per il menu a tendina: Svizzera, Italia, poi i paesi europei,
poi tutti gli altri (ordine alfabetico in ciascun gruppo)."""

PRIMI = ["Svizzera", "Italia"]

EUROPA = sorted([
    "Albania", "Andorra", "Austria", "Belgio", "Bielorussia", "Bosnia ed Erzegovina", "Bulgaria", "Cipro",
    "Città del Vaticano", "Croazia", "Danimarca", "Estonia", "Finlandia", "Francia", "Germania", "Grecia",
    "Irlanda", "Islanda", "Kosovo", "Lettonia", "Liechtenstein", "Lituania", "Lussemburgo", "Macedonia del Nord",
    "Malta", "Moldavia", "Monaco", "Montenegro", "Norvegia", "Paesi Bassi", "Polonia", "Portogallo",
    "Regno Unito", "Repubblica Ceca", "Romania", "Russia", "San Marino", "Serbia", "Slovacchia", "Slovenia",
    "Spagna", "Svezia", "Ucraina", "Ungheria",
], key=str.casefold)

ALTRI = sorted([
    "Afghanistan", "Algeria", "Angola", "Arabia Saudita", "Argentina", "Armenia", "Australia", "Azerbaigian",
    "Bangladesh", "Benin", "Bolivia", "Brasile", "Burkina Faso", "Camerun", "Canada", "Capo Verde", "Cile",
    "Cina", "Colombia", "Congo (Rep. Dem.)", "Corea del Sud", "Costa d'Avorio", "Costa Rica", "Cuba", "Ecuador",
    "Egitto", "El Salvador", "Emirati Arabi Uniti", "Eritrea", "Etiopia", "Filippine", "Georgia", "Ghana",
    "Giappone", "Giordania", "Guatemala", "Guinea", "Haiti", "Honduras", "India", "Indonesia", "Iran", "Iraq",
    "Israele", "Kazakistan", "Kenya", "Kirghizistan", "Kuwait", "Libano", "Libia", "Madagascar", "Malaysia",
    "Mali", "Marocco", "Mauritius", "Messico", "Mongolia", "Nepal", "Nicaragua", "Nigeria", "Nuova Zelanda",
    "Pakistan", "Panama", "Paraguay", "Perù", "Repubblica Dominicana", "Ruanda", "Senegal", "Siria", "Somalia",
    "Sri Lanka", "Stati Uniti", "Sudafrica", "Sudan", "Tailandia", "Taiwan", "Tanzania", "Togo", "Tunisia",
    "Turchia", "Uganda", "Uruguay", "Uzbekistan", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
], key=str.casefold)

NAZIONALITA = PRIMI + EUROPA + ALTRI
