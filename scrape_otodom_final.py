import asyncio
import pandas as pd
from playwright.async_api import async_playwright
import re

MAX_ADS = 2000
BACKUP_INTERVAL = 100

async def scrape_detailed_otodom():
    base_url = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/slaskie/katowice/katowice"
    listings = []
    seen_urls = set()
    total_collected = 0
    page_number = 1

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context()
        page = await context.new_page()

        while total_collected < MAX_ADS:
            url = f"{base_url}?page={page_number}"
            print(f"\n Przetwarzam stronę {page_number}: {url}")
            await page.goto(url)
            await page.wait_for_timeout(3000)

            links = await page.query_selector_all("a[data-cy='listing-item-link']")
            if not links:
                print("Brak ogłoszeń na stronie, kończę.")
                break

            offer_urls = []
            for link in links:
                href = await link.get_attribute("href")
                if href and "/pl/oferta/" in href:
                    full_url = "https://www.otodom.pl" + href.split("?")[0]
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        offer_urls.append(full_url)

            print(f"Znaleziono {len(offer_urls)} nowych ogłoszeń.")

            for offer_url in offer_urls:
                if total_collected >= MAX_ADS:
                    break

                offer_page = await context.new_page()
                try:
                    await offer_page.goto(offer_url, timeout=15000)
                    await offer_page.wait_for_timeout(2500)

                    data = {
                        "url": offer_url,
                        "title": "brak informacji",
                        "price": "brak informacji",
                        "location": "brak informacji",
                        "area_m2": "brak informacji",
                        "rooms": "brak informacji",
                        "floor": "brak informacji",
                        "market_type": "brak informacji",
                        "year_built": "brak informacji",
                        "finish": "brak informacji",
                        "heating": "brak informacji",
                        "rent": "brak informacji",
                        "ownership": "brak informacji",
                        "available_from": "brak informacji",
                        "advertiser_type": "brak informacji",
                        "extras": "brak informacji",
                        "price_per_m2": "brak informacji",
                        "elevator": "brak informacji",
                        "building_material": "brak informacji",
                        "window_type": "brak informacji",
                        "building_type": "brak informacji",
                        "energy_certificate": "brak informacji",
                        "security_features": "brak informacji"
                    }

                    # Tytuł
                    title_el = await offer_page.query_selector("h1")
                    if title_el:
                        data["title"] = (await title_el.inner_text()).strip()

                    # Cena
                    price_el = await offer_page.query_selector("strong[data-cy='adPageHeaderPrice']")
                    if price_el:
                        data["price"] = (await price_el.inner_text()).strip()

                    # Lokalizacja
                    loc_el = await offer_page.query_selector("a[href='#map']")
                    if loc_el:
                        data["location"] = (await loc_el.inner_text()).strip()

                    # Cena za m2
                    price_m2_el = await offer_page.query_selector("div[aria-label='Cena za metr kwadratowy']")
                    if price_m2_el:
                        txt = (await price_m2_el.inner_text()).strip()
                        match = re.search(r"([\d\s]+)", txt)
                        if match:
                            data["price_per_m2"] = int(match.group(1).replace(" ", ""))

                    # Metraż 
                    details_texts = await offer_page.query_selector_all("div.css-1ftqasz")
                    for el in details_texts:
                        txt = (await el.inner_text()).strip().lower()
                        if "m²" in txt:
                            match = re.search(r"([\d.,]+)", txt.replace(",", "."))
                            if match:
                                data["area_m2"] = float(match.group(1))
                        elif "pok" in txt:
                            match = re.search(r"(\d+)", txt)
                            if match:
                                data["rooms"] = int(match.group(1))

                    # Szczegóły (label + value)
                    detail_blocks = await offer_page.query_selector_all("div:has(p):has(p)")
                    for block in detail_blocks:
                        try:
                            ps = await block.query_selector_all("p")
                            if len(ps) != 2:
                                continue
                            label = (await ps[0].inner_text()).strip().lower().replace(":", "")
                            value = (await ps[1].inner_text()).strip()

                            if "piętro" in label:
                                data["floor"] = value
                            elif "rynek" in label:
                                data["market_type"] = value
                            elif "rok budowy" in label:
                                match = re.search(r"(19\d{2}|20\d{2})", value)
                                data["year_built"] = int(match.group(1)) if match else value
                            elif "stan wykończenia" in label:
                                data["finish"] = value
                            elif "ogrzewanie" in label:
                                data["heating"] = value
                            elif "czynsz" in label:
                                data["rent"] = value
                            elif "forma własności" in label:
                                data["ownership"] = value
                            elif "dostępne od" in label:
                                data["available_from"] = value
                            elif "typ ogłoszeniodawcy" in label:
                                data["advertiser_type"] = value
                            elif "informacje dodatkowe" in label:
                                data["extras"] = value
                            elif "winda" in label:
                                data["elevator"] = value
                            elif "materiał budynku" in label:
                                data["building_material"] = value
                            elif "okna" in label:
                                data["window_type"] = value
                            elif "certyfikat energetyczny" in label:
                                data["energy_certificate"] = value
                            elif "rodzaj zabudowy" in label:
                                data["building_type"] = value
                            elif "bezpieczeństwo" in label:
                                data["security_features"] = value
                        except:
                            continue

                    # Czyszczenie extras
                    for key in ["extras"]:
                        if data[key] and isinstance(data[key], str):
                            data[key] = data[key].replace("\n", ", ").strip()

                    listings.append(data)
                    total_collected += 1
                    print(f"Zebrano: {total_collected} | {data['title'][:40]}")

                    # Backup co 100
                    if total_collected % BACKUP_INTERVAL == 0:
                        pd.DataFrame(listings).to_csv("katowice_partial.csv", index=False, encoding="utf-8-sig")
                        print("Zapisano backup do katowice_partial.csv")

                except Exception as e:
                    print(f"Błąd: {e}")
                finally:
                    await offer_page.close()
                    await asyncio.sleep(0.5)

            page_number += 1

        await browser.close()

    pd.DataFrame(listings).to_csv("katowice_full.csv", index=False, encoding="utf-8-sig")
    print("Gotowe! Dane zapisane do katowice_full.csv")

if __name__ == "__main__":
    asyncio.run(scrape_detailed_otodom())
