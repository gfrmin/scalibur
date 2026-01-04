"""Tests for decode module."""

import pytest

from decode import ScaleReading, BodyComposition, decode_packet, calculate_body_composition


class TestDecodePacket:
    """Tests for decode_packet function."""

    def test_decode_complete_measurement(self):
        """Decode a complete measurement packet."""
        # New layout: weight=82.5kg (825=0x0339), impedance=501.9ohm (5019=0x139B)
        # user_id=2, status=0x21 (complete with impedance)
        packet = bytes([
            0x03, 0x39,  # weight = 825 (82.5 kg)
            0x13, 0x9B,  # impedance = 5019 (501.9 ohm)
            0x00, 0x02,  # user_id = 2
            0x21,        # status (complete)
        ])

        result = decode_packet(0, packet)

        assert result is not None
        assert result.weight_kg == pytest.approx(82.5, rel=0.01)
        assert result.impedance_raw == 5019
        assert result.impedance_ohm == pytest.approx(501.9, rel=0.01)
        assert result.user_id == 2
        assert result.is_complete is True
        assert result.is_locked is True

    def test_decode_incomplete_measurement(self):
        """Decode an incomplete measurement (still weighing)."""
        # Status 0x20 with impedance > 0 means still measuring
        packet = bytes([
            0x03, 0x35,  # weight = 821 (82.1 kg)
            0x13, 0x99,  # impedance = 5017 (501.7 ohm)
            0x00, 0x02,  # user_id = 2
            0x20,        # status (not complete - has impedance but status says still measuring)
        ])

        result = decode_packet(0, packet)

        assert result is not None
        assert result.is_complete is False
        assert result.is_locked is False

    def test_decode_no_impedance(self):
        """Decode packet with no impedance reading (weight-only mode)."""
        # Status 0x20 with impedance=0 is "complete" (user not barefoot)
        packet = bytes([
            0x03, 0x35,  # weight = 821 (82.1 kg)
            0x00, 0x00,  # no impedance
            0x00, 0x01,  # user_id = 1
            0x20,        # status (weight-only complete)
        ])

        result = decode_packet(0, packet)

        assert result is not None
        assert result.impedance_raw == 0
        assert result.impedance_ohm is None
        assert result.is_complete is True  # 0x20 + impedance=0 means complete

    def test_decode_packet_too_short(self):
        """Return None for packets that are too short."""
        packet = bytes([0x03, 0x35, 0x00])  # only 3 bytes, need 7
        assert decode_packet(0, packet) is None

    def test_decode_empty_packet(self):
        """Return None for empty packets."""
        assert decode_packet(0, b"") is None

    def test_decode_weight_below_threshold(self):
        """Return None for weights below 30kg threshold."""
        # weight=25.0kg (250=0x00FA), valid format but below threshold
        packet = bytes([
            0x00, 0xFA,  # weight = 250 (25.0 kg) - below 30kg threshold
            0x13, 0x9B,  # impedance = 5019 (501.9 ohm)
            0x00, 0x02,  # user_id = 2
            0x21,        # status (complete)
        ])
        assert decode_packet(0, packet) is None


class TestCalculateBodyComposition:
    """Tests for calculate_body_composition function."""

    def test_male_body_composition(self):
        """Calculate body composition for male profile."""
        result = calculate_body_composition(
            weight_kg=82.5,
            impedance_ohm=501.9,
            height_cm=173,
            age=43,
            gender="male",
        )

        assert isinstance(result, BodyComposition)
        # Sanity checks - values should be in reasonable ranges
        assert 10 < result.body_fat_pct < 40
        assert result.fat_mass_kg > 0
        assert result.lean_mass_kg > 0
        assert result.fat_mass_kg + result.lean_mass_kg == pytest.approx(82.5, rel=0.1)
        assert 40 < result.body_water_pct < 70
        assert result.muscle_mass_kg > 0
        assert result.bone_mass_kg > 0
        assert 1500 < result.bmr_kcal < 2500
        assert 20 < result.bmi < 35

    def test_female_body_composition(self):
        """Calculate body composition for female profile."""
        result = calculate_body_composition(
            weight_kg=65.0,
            impedance_ohm=550.0,
            height_cm=165,
            age=35,
            gender="female",
        )

        assert isinstance(result, BodyComposition)
        # Female-specific sanity checks
        assert 15 < result.body_fat_pct < 45
        assert result.lean_mass_kg > 0
        assert 1200 < result.bmr_kcal < 2000

    def test_bmi_calculation(self):
        """BMI should be calculated correctly."""
        result = calculate_body_composition(
            weight_kg=70.0,
            impedance_ohm=500.0,
            height_cm=175,
            age=30,
            gender="male",
        )

        # BMI = 70 / (1.75^2) = 22.86
        assert result.bmi == pytest.approx(22.9, rel=0.1)

    def test_values_are_rounded(self):
        """All percentage and mass values should be rounded to 1 decimal."""
        result = calculate_body_composition(
            weight_kg=82.5,
            impedance_ohm=501.9,
            height_cm=173,
            age=43,
            gender="male",
        )

        # Check that values have at most 1 decimal place
        assert result.body_fat_pct == round(result.body_fat_pct, 1)
        assert result.fat_mass_kg == round(result.fat_mass_kg, 1)
        assert result.lean_mass_kg == round(result.lean_mass_kg, 1)
        assert result.bmi == round(result.bmi, 1)
        # BMR should be integer
        assert result.bmr_kcal == int(result.bmr_kcal)
