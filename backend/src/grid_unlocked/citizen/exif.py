import io

from PIL import Image
from PIL.ExifTags import GPSTAGS

_GPS_IFD_TAG = 0x8825


def extract_gps_from_exif(photo_bytes: bytes) -> tuple[float, float] | None:
    """Returns (lat, lon) in decimal degrees, or None if no readable GPS EXIF tag."""
    try:
        img = Image.open(io.BytesIO(photo_bytes))
        exif = img.getexif()
        gps_ifd = exif.get_ifd(_GPS_IFD_TAG)
        if not gps_ifd:
            return None
        gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
        lat = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
        lon = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
        if lat is None or lon is None:
            return None
        return lat, lon
    except Exception:
        return None


def _dms_to_decimal(dms, ref) -> float | None:
    if not dms or not ref:
        return None
    try:
        deg, minutes, seconds = (float(v) for v in dms)
    except (TypeError, ValueError):
        return None
    value = deg + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        value = -value
    return value


def strip_exif_except_gps(photo_bytes: bytes) -> bytes:
    """Spec: retain photos with EXIF PII stripped except GPS."""
    try:
        img = Image.open(io.BytesIO(photo_bytes))
        exif = img.getexif()
        gps_ifd = exif.get_ifd(_GPS_IFD_TAG)
        new_exif = Image.Exif()
        if gps_ifd:
            new_exif.get_ifd(_GPS_IFD_TAG).update(gps_ifd)
        out = io.BytesIO()
        img.save(out, format=img.format, exif=new_exif.tobytes())
        return out.getvalue()
    except Exception:
        return photo_bytes
