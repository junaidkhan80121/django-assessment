import csv
import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from route.services.geocoding import geocode_place, MapboxUnavailableError


class Command(BaseCommand):
    help = "Build data/city_centroids.json by geocoding unique City,State pairs from the fuel CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default="",
            help="Optional path to fuel CSV. Defaults to fuel-prices-for-be-assessment.csv (or data/fuel_prices.csv).",
        )
        parser.add_argument(
            "--sleep",
            dest="sleep_seconds",
            type=float,
            default=0.05,
            help="Sleep between geocoding calls to be polite to the API.",
        )

    def handle(self, *args, **options):
        csv_arg = (options.get("csv_path") or "").strip()
        sleep_seconds = float(options.get("sleep_seconds") or 0.0)

        if csv_arg:
            csv_path = Path(csv_arg)
        else:
            csv_path = Path(settings.BASE_DIR) / "fuel-prices-for-be-assessment.csv"
            if not csv_path.exists():
                csv_path = Path(settings.BASE_DIR) / "data" / "fuel_prices.csv"

        if not csv_path.exists():
            raise SystemExit(f"Fuel CSV not found: {csv_path}")

        out_path = Path(settings.BASE_DIR) / "data" / "city_centroids.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        existing = {}
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        pairs = set()
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                city = (row.get("City") or "").strip()
                state = (row.get("State") or "").strip()
                if not city or not state:
                    continue
                key = f"{city.lower()},{state.lower()}"
                if key in existing:
                    continue
                pairs.add((city, state, key))

        self.stdout.write(f"Unique city/state to geocode: {len(pairs)} (existing cache: {len(existing)})")

        done = 0
        failed = 0
        for city, state, key in sorted(pairs, key=lambda x: x[2]):
            query = f"{city}, {state}"
            try:
                lon, lat = geocode_place(query)
                existing[key] = [lon, lat]
                done += 1
            except (ValueError, MapboxUnavailableError):
                failed += 1
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            if (done + failed) % 100 == 0:
                out_path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
                self.stdout.write(f"Progress: ok={done} failed={failed} cached={len(existing)}")

        out_path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Done. ok={done} failed={failed} wrote {out_path}"))

