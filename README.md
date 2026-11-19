# PS5 Pro stock alert

Checks PS5 Pro (standard console, no bundles) stock and sends a Telegram message
when a retailer goes from **out of stock → in stock**, **sold by the retailer itself**,
at or under **£800 (UK)** / **€910 (DE)**.

## Retailers checked

| Retailer | Page |
|---|---|
| PlayStation Direct UK | https://direct.playstation.com/en-gb/buy-consoles/playstation5-pro-console-2-tb |
| PlayStation Direct DE | https://direct.playstation.com/de-de/buy-consoles/playstation5-pro-console-2-tb |

## Dropped (block automated checks)

- **Argos**: "Access Denied" (Akamai bot protection)
- **Currys**: Cloudflare "checking your connection" challenge
- **Smyths**: Imperva "Pardon Our Interruption" bot page
- **MediaMarkt** and **Saturn**: CAPTCHA page
- **Otto**: rejects script requests (HTTP 400)
- **Game**: never responds to script requests (times out)
- **Amazon UK** and **Amazon DE**: worked from home, but show a CAPTCHA every time from GitHub's servers

## Files

- `check_stock.py`: the checker
- `notify.py`: Telegram sending (`python3 notify.py test` sends a test message)
- `state.json`: last known status, so you don't get repeat alerts
- `.env`: your token and chat ID (**local only, gitignored**)
- `.github/workflows/check-stock.yml`: runs the check on GitHub every 5 minutes
