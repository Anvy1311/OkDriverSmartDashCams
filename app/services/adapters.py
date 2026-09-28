from datetime import datetime, timezone
from html import escape
from typing import Any

from ..models import Camera


class SimulatedCameraAdapter:
    protocol = "SIMULATOR"
    label = "Simulated source"

    def __init__(self, camera: Camera) -> None:
        self.camera = camera

    def render(self, timestamp: datetime | None = None) -> str:
        moment = timestamp or datetime.now(timezone.utc)
        stamp = moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        title = escape(self.camera.name)
        camera_id = escape(self.camera.camera_id)
        status = escape(self.camera.status)
        color = "#35d07f" if self.camera.status == "ONLINE" else "#f0b34b"
        if self.camera.status == "OFFLINE":
            color = "#e35b65"
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
<defs>
<linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#15243d"/><stop offset="1" stop-color="#080d18"/></linearGradient>
<linearGradient id="road" x1="0" x2="1"><stop offset="0" stop-color="#202a3a"/><stop offset="0.5" stop-color="#39485a"/><stop offset="1" stop-color="#202a3a"/></linearGradient>
<filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="960" height="540" fill="url(#sky)"/>
<rect x="0" y="300" width="960" height="240" fill="url(#road)"/>
<path d="M0 420H960" stroke="#f7d36b" stroke-width="5" stroke-dasharray="38 28" opacity=".9"/>
<path d="M0 470H960" stroke="#64748b" stroke-width="3" opacity=".8"/>
<path d="M0 345H960" stroke="#64748b" stroke-width="3" opacity=".8"/>
<rect x="28" y="28" width="260" height="58" rx="10" fill="#0a1220" fill-opacity=".88" stroke="#35d07f" stroke-opacity=".65"/>
<text x="48" y="54" fill="#e8f1ff" font-family="Arial,sans-serif" font-size="17" font-weight="700">{title}</text>
<text x="48" y="76" fill="{color}" font-family="Arial,sans-serif" font-size="13">{camera_id} · {self.protocol} · {status}</text>
<rect x="714" y="28" width="220" height="58" rx="10" fill="#0a1220" fill-opacity=".88"/>
<text x="734" y="53" fill="#9fb0c9" font-family="Arial,sans-serif" font-size="12">NEAR-LIVE SIMULATED FEED</text>
<text x="734" y="75" fill="#e8f1ff" font-family="Arial,sans-serif" font-size="14">{stamp}</text>
<g filter="url(#glow)"><rect x="78" y="385" width="130" height="46" rx="10" fill="#35d07f"/><rect x="98" y="368" width="90" height="22" rx="8" fill="#9af0bd"/><circle cx="106" cy="435" r="13" fill="#101722"/><circle cx="180" cy="435" r="13" fill="#101722"/><text x="92" y="414" fill="#092117" font-family="Arial,sans-serif" font-size="14" font-weight="700">ANPR</text></g>
<animateTransform attributeName="transform" attributeType="XML" type="translate" values="0 0;660 0;0 0" dur="12s" repeatCount="indefinite"/>
<rect x="38" y="500" width="884" height="4" rx="2" fill="#35d07f" opacity=".7"/>
</svg>'''


class RtspSimulatedAdapter(SimulatedCameraAdapter):
    protocol = "RTSP"
    label = "RTSP simulator adapter"


class OnvifSimulatedAdapter(SimulatedCameraAdapter):
    protocol = "ONVIF"
    label = "ONVIF simulator adapter"


class VendorApiSimulatedAdapter(SimulatedCameraAdapter):
    protocol = "VENDOR_API"
    label = "Vendor API simulator adapter"


class HlsSimulatedAdapter(SimulatedCameraAdapter):
    protocol = "HLS"
    label = "HLS simulator adapter"


def get_adapter(camera: Camera) -> SimulatedCameraAdapter:
    protocol = (camera.source_protocol or "").upper()
    adapters: dict[str, type[SimulatedCameraAdapter]] = {
        "RTSP": RtspSimulatedAdapter,
        "ONVIF": OnvifSimulatedAdapter,
        "VENDOR_API": VendorApiSimulatedAdapter,
        "HLS": HlsSimulatedAdapter,
    }
    adapter_class = adapters.get(protocol, SimulatedCameraAdapter)
    return adapter_class(camera)


def adapter_descriptor(camera: Camera) -> dict[str, Any]:
    adapter = get_adapter(camera)
    return {
        "protocol": adapter.protocol,
        "label": adapter.label,
        "mode": "simulated",
        "stream_path": f"/api/v1/cameras/{camera.camera_id}/stream",
    }
