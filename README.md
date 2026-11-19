# PS5 Pro stock alert

Checks PS5 Pro (standard console, no bundles) stock and sends a Telegram message
when a retailer goes from **out of stock → in stock**, **sold by the retailer itself**,
at or under **£800 (UK)** / **€910 (DE)**.

## Retailers checked

| Retailer | Page |
|---|---|
| PlayStation Direct UK | https://direct.playstation.com/en-gb/buy-consoles/playstation5-pro-console-2-tb |
| PlayStation Direct DE | https://direct.playstation.com/de-de/buy-consoles/playstation5-pro-console-2-tb |
| Amazon UK (CFI-7021) | https://www.amazon.co.uk/dp/B0DJH2NS6R |
| Amazon UK (newer listing) | https://www.amazon.co.uk/dp/B0FR94FV8J |
| Amazon DE (CFI-7021) | https://www.amazon.de/dp/B0DHSV68YZ |
| Amazon DE (CFI-7121) | https://www.amazon.de/dp/B0FRYBZR91 |

Amazon only alerts when the seller is Amazon itself, not marketplace sellers.

## Dropped (block automated checks)

- **Argos**: "Access Denied" (Akamai bot protection)
- **Currys**: Cloudflare "checking your connection" challenge
- **Smyths**: Imperva "Pardon Our Interruption" bot page
- **MediaMarkt** and **Saturn**: CAPTCHA page
- **Otto**: rejects script requests (HTTP 400)
- **Game**: never responds to script requests (times out)

## Files

- `check_stock.py`: the checker
- `notify.py`: Telegram sending (`python3 notify.py test` sends a test message)
- `state.json`: last known status, so you don't get repeat alerts
- `.env`: your token and chat ID (**local only, gitignored**)
- `.github/workflows/check-stock.yml`: runs the check on GitHub every 5 minutes
