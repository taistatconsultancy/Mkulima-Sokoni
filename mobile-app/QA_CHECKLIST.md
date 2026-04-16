# Mobile App QA Checklist

## Device Matrix

- Android Chrome (latest)
- Android Chrome (low/mid device)
- iOS Safari (latest)

## Functional Flows

- Buyer: browse -> add to cart -> checkout -> messages
- Farmer: products -> tenders -> orders -> messages
- Agro-dealer: inventory -> orders -> tenders

## PWA

- Install prompt appears on supported browsers
- iOS install guidance visible when not installed
- Home screen launch opens in standalone mode

## Offline/Network

- App shell loads while offline
- API calls show graceful error notices when offline
- Recovers correctly after reconnect

## Performance/UX

- No horizontal scrolling on core screens
- Touch targets are usable (>=44px)
- Sticky CTA is visible and not blocking content

## Session

- Role persistence survives page reload
- Existing localStorage user session still drives API requests

## Release Decision Note

- Current folder supports PWA-only release immediately.
- If store packaging is needed later, use Capacitor wrapper around `mobile-app/`.
