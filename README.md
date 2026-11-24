# Image Extractor Pro — Vercel

A responsive webpage for finding publicly exposed image URLs on webpages and direct image links.

## Deploy
1. Upload the contents of this folder to a GitHub repository.
2. Import the repository at https://vercel.com/new.
3. Choose Other if asked for a framework. Leave build/output commands empty.
4. Deploy. No environment variables are required.

## Use
Open the deployed site, paste a public webpage URL or direct image URL, and press **Extract images**. Preview results and copy image URLs for your Telegram bot.

## Extraction
Scans Open Graph/Twitter preview metadata, standard and lazy image attributes, responsive image sets, picture sources, image links/preloads, inline CSS backgrounds, and image URLs embedded in page source. It returns up to 200 unique URL candidates and removes exact URL duplicates (including tracking parameters/fragments).

## Limitations and safety
This scans the HTML/source returned by the website; it does not run page JavaScript, sign in, bypass paywalls, or bypass anti-bot restrictions. Google Images and Pinterest may expose only thumbnails or require JavaScript/login, so original images cannot always be obtained. Some sites intentionally hide or block images. Use only images you have permission to download or share.

Public deployments should add rate limiting and usage limits. The endpoint rejects local/private network destinations.
