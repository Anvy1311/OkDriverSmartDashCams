# Seed Data

The seed module creates:

- `admin` and `operator` users with development-only passwords.
- Six camera sources across Ahmedabad and Gandhinagar using RTSP and ONVIF simulator adapters.
- Online, degraded, and offline examples for operational clarity.
- Three synthetic watchlist records: two vehicles and one person.
- Three chronological `GJ01AB1234` ANPR observations, which create auditable alerts and a route.

The 50-camera bulk sample is [`cameras_sample.csv`](../data/cameras_sample.csv). Convert the CSV rows to the JSON `CameraCreate` contract and submit them to `POST /api/v1/cameras/bulk` when evaluating a larger registry. The rows are synthetic metadata and contain no real camera credentials.
