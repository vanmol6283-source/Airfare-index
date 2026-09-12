import urllib.robotparser
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import socket

# Global socket timeout
socket.setdefaulttimeout(5)

WEBSITES = {
    "MakeMyTrip": "https://www.makemytrip.com/flight/search?itinerary=DEL-BOM-14/10/2026&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E",
    "ClearTrip": "https://www.cleartrip.com/flights/results?from=DEL&to=BOM&depart_date=14/10/2026&adults=1&childs=0&infants=0&class=Economy",
    "Yatra": "https://flight.yatra.com/air-search-ui/dom2/trigger?type=O&viewName=normal&flexi=0&noOfSegments=1&origin=DEL&originCountry=IN&destination=BOM&destinationCountry=IN&flight_depart_date=14/10/2026&ADT=1&CHD=0&INF=0&class=Economy",
    "Goibibo": "https://www.goibibo.com/flights/air-DEL-BOM-20261014--1-0-0-E-D/",
    "EaseMyTrip": "https://flight.easemytrip.com/FlightList/Index?seg1=DELBOM&trvldt1=14/10/2026&TravelType=1&PassengerCount=1-0-0-0&Cbntype=E",
    "Ixigo": "https://www.ixigo.com/search/result/flight?from=DEL&to=BOM&date=14102026&adults=1&children=0&infants=0&class=e",
    "Paytm Flights": "https://tickets.paytm.com/flights/flightSearch/DEL-Delhi/BOM-Mumbai/1/0/0/E/2026-10-14",
    "IndiGo": "https://book.goindigo.in/booking/SearchTrips?origin=DEL&destination=BOM&departureDate=2026-10-14&adults=1",
    "Air India": "https://www.airindia.com/in/en/book/search-flights.html",
    "Akasa Air": "https://www.akasaair.com/booking/select-flights?from=DEL&to=BOM&date=2026-10-14",
    "SpiceJet": "https://www.spicejet.com/search?from=DEL&to=BOM&date=2026-10-14",
    "Air India Express": "https://www.airindiaexpress.com/search-results?from=DEL&to=BOM&date=2026-10-14"
}

def check_site(name, search_url):
    parsed = urllib.parse.urlparse(search_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    
    try:
        rp.read()
        allowed_all = rp.can_fetch("*", search_url)
        allowed_bot = rp.can_fetch("AirfarePriceIndexBot", search_url)
        
        if allowed_all or allowed_bot:
            status = "[OK] Easy (Allowed in robots.txt)"
        else:
            status = "[BLOCKED] Hard (Blocked in robots.txt)"
        return f"{name.ljust(18)} | {status.ljust(35)} | {robots_url}"
    except Exception as e:
        # Many sites block urllib's default User-Agent with 403 or Timeout
        # In our scraper pipeline we fallback to allowed on fetch errors, so we'd call it "Medium".
        return f"{name.ljust(18)} | [MEDIUM] (Error fetching robots)  | {robots_url} - {str(e)[:30]}"

print("Checking Indian Airfare Websites for Bot Compliance (robots.txt)...")
print("-" * 105)
print(f"{'Website'.ljust(18)} | {'Bot Access (Search Pages)'.ljust(35)} | {'Robots.txt URL'}")
print("-" * 105)

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(lambda item: check_site(item[0], item[1]), WEBSITES.items()))

for r in results:
    print(r)
print("-" * 105)
