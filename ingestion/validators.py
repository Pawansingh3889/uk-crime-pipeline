"""Data validation for crime pipeline ingestion.

Inspired by PyCon DE 2026 talk: "Ship Data with Confidence" (Sequeira, GetYourGuide).
Declarative validation applied before warehouse load.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

import pandas as pd


# Official Police UK crime categories
POLICE_UK_CATEGORIES = frozenset({
    "anti-social-behaviour",
    "bicycle-theft",
    "burglary",
    "criminal-damage-arson",
    "drugs",
    "other-crime",
    "other-theft",
    "possession-of-weapons",
    "public-order",
    "robbery",
    "shoplifting",
    "theft-from-the-person",
    "vehicle-crime",
    "violent-crime",
})

# UK bounding box (approximate)
UK_LAT_MIN, UK_LAT_MAX = 49.9, 60.9
UK_LNG_MIN, UK_LNG_MAX = -8.2, 1.8

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


@dataclass
class CheckResult:
    """Outcome of a single validation check."""

    name: str
    passed: bool
    message: str


@dataclass
class ValidationResult:
    """Aggregate result of all validation checks for a batch."""

    city: str
    month: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        details = "; ".join(
            f"{c.name}: {c.message}" for c in self.checks if not c.passed
        )
        base = f"[{status}] {self.city} {self.month} \u2014 {len(self.checks)} checks"
        if details:
            base += f" ({details})"
        return base


class CrimeBatchValidator:
    """Fluent validator for a crime data batch (one city/month).

    Usage::

        result = (
            CrimeBatchValidator(df, city="London", month="2024-05")
            .expect_row_count_gte(50)
            .expect_no_null_crime_ids()
            .expect_coordinates_within_uk()
            .expect_valid_categories()
            .expect_month_format()
            .validate()
        )
    """

    def __init__(self, df: pd.DataFrame, *, city: str, month: str) -> None:
        self._df = df
        self._city = city
        self._month = month
        self._checks: List[CheckResult] = []

    # -- chainable expectation methods ----------------------------------------

    def expect_row_count_gte(self, minimum: int = 50) -> CrimeBatchValidator:
        """Expect at least *minimum* rows in the batch."""
        count = len(self._df)
        passed = count >= minimum
        self._checks.append(
            CheckResult(
                name="row_count_gte",
                passed=passed,
                message=f"{count} rows (min {minimum})",
            )
        )
        return self

    def expect_no_null_crime_ids(self) -> CrimeBatchValidator:
        """Expect zero null values in the crime_id column."""
        if "crime_id" not in self._df.columns:
            self._checks.append(
                CheckResult(
                    name="no_null_crime_ids",
                    passed=False,
                    message="crime_id column missing",
                )
            )
            return self
        null_count = int(self._df["crime_id"].isna().sum())
        empty_count = int((self._df["crime_id"] == "").sum())
        total_bad = null_count + empty_count
        passed = total_bad == 0
        self._checks.append(
            CheckResult(
                name="no_null_crime_ids",
                passed=passed,
                message=f"{total_bad} null/empty crime_ids",
            )
        )
        return self

    def expect_coordinates_within_uk(self) -> CrimeBatchValidator:
        """Expect latitude/longitude within UK bounds when present."""
        if "latitude" not in self._df.columns or "longitude" not in self._df.columns:
            self._checks.append(
                CheckResult(
                    name="coords_within_uk",
                    passed=True,
                    message="coordinate columns absent \u2014 skipped",
                )
            )
            return self

        lat = pd.to_numeric(self._df["latitude"], errors="coerce")
        lng = pd.to_numeric(self._df["longitude"], errors="coerce")

        has_coords = lat.notna() & lng.notna()
        if has_coords.sum() == 0:
            self._checks.append(
                CheckResult(
                    name="coords_within_uk",
                    passed=True,
                    message="no rows with coordinates \u2014 skipped",
                )
            )
            return self

        out_of_bounds = has_coords & ~(
            (lat >= UK_LAT_MIN)
            & (lat <= UK_LAT_MAX)
            & (lng >= UK_LNG_MIN)
            & (lng <= UK_LNG_MAX)
        )
        bad = int(out_of_bounds.sum())
        passed = bad == 0
        self._checks.append(
            CheckResult(
                name="coords_within_uk",
                passed=passed,
                message=f"{bad} rows outside UK bounds",
            )
        )
        return self

    def expect_valid_categories(self) -> CrimeBatchValidator:
        """Expect category values belong to the known Police UK set."""
        if "category" not in self._df.columns:
            self._checks.append(
                CheckResult(
                    name="valid_categories",
                    passed=False,
                    message="category column missing",
                )
            )
            return self

        unknown = set(self._df["category"].dropna().unique()) - POLICE_UK_CATEGORIES
        passed = len(unknown) == 0
        self._checks.append(
            CheckResult(
                name="valid_categories",
                passed=passed,
                message=f"unknown categories: {unknown}" if unknown else "all valid",
            )
        )
        return self

    def expect_month_format(self) -> CrimeBatchValidator:
        """Expect month column matches YYYY-MM format."""
        if "month" not in self._df.columns:
            self._checks.append(
                CheckResult(
                    name="month_format",
                    passed=False,
                    message="month column missing",
                )
            )
            return self

        bad_formats = [
            v
            for v in self._df["month"].dropna().unique()
            if not MONTH_PATTERN.match(str(v))
        ]
        passed = len(bad_formats) == 0
        self._checks.append(
            CheckResult(
                name="month_format",
                passed=passed,
                message=f"bad formats: {bad_formats}" if bad_formats else "all valid",
            )
        )
        return self

    # -- terminal method ------------------------------------------------------

    def validate(self) -> ValidationResult:
        """Run all registered expectations and return the result."""
        return ValidationResult(
            city=self._city,
            month=self._month,
            checks=list(self._checks),
        )


def validate_batch(records: list, *, city: str, month: str) -> ValidationResult:
    """Convenience wrapper: validate a list of crime dicts.

    Converts the raw API records to a DataFrame, runs the full suite of
    expectations, and returns a :class:`ValidationResult`.
    """
    if not records:
        return ValidationResult(
            city=city,
            month=month,
            checks=[
                CheckResult(
                    name="row_count_gte",
                    passed=False,
                    message="0 rows (min 50)",
                )
            ],
        )

    rows = []
    for c in records:
        rows.append(
            {
                "crime_id": str(c.get("id", "")),
                "category": c.get("category", ""),
                "latitude": c.get("latitude"),
                "longitude": c.get("longitude"),
                "month": c.get("month", ""),
            }
        )
    df = pd.DataFrame(rows)

    result = (
        CrimeBatchValidator(df, city=city, month=month)
        .expect_row_count_gte(50)
        .expect_no_null_crime_ids()
        .expect_coordinates_within_uk()
        .expect_valid_categories()
        .expect_month_format()
        .validate()
    )
    return result
