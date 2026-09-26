"""Tests for recom.fw_update and recom.fw_image against a simulated device.

    cd host && pytest
"""

import pytest
from fw_sim import SimDevice, mcuboot_image, sim_device, sim_opener

from recom import fw_update
from recom.device import FwResult, FwState
from recom.exceptions import RecomDeviceException
from recom.fw_image import ImageError, ImageVersion, parse_mcuboot


@pytest.fixture
def image_file(tmp_path):
    def make(**kwargs):
        path = tmp_path / "fw.bin"
        path.write_bytes(mcuboot_image(**kwargs))
        return str(path)
    return make


def run(sim, path, **kwargs):
    stages = []
    result = fw_update.update_firmware(
        sim_device(sim), path, open_device=sim_opener(sim),
        progress=lambda stage, done, total: stages.append(stage), **kwargs)
    return result, stages


# ------------------------------------------------------------ fw_image


def test_parse_mcuboot_version():
    assert parse_mcuboot(mcuboot_image(version=(3, 1, 4, 15))) == ImageVersion(3, 1, 4, 15)


def test_parse_mcuboot_with_protected_tlvs():
    assert parse_mcuboot(mcuboot_image(prot_tlvs=True)) == ImageVersion(1, 2, 3, 4)


def test_parse_rejects_unsigned_binary():
    with pytest.raises(ImageError, match="magic"):
        parse_mcuboot(b"\x00" * 4096)


def test_parse_rejects_truncated_image():
    with pytest.raises(ImageError):
        parse_mcuboot(mcuboot_image()[:-10])


def test_parse_rejects_trailing_bytes():
    with pytest.raises(ImageError, match="size"):
        parse_mcuboot(mcuboot_image() + b"\xff" * 16)


def test_version_string():
    assert str(ImageVersion(1, 2, 3, 4)) == "1.2.3+4"


# ------------------------------------------------------------ happy paths


def test_test_install_updates_and_waits_for_confirmation(image_file):
    sim = SimDevice(running=(1, 0, 0, 0))
    path = image_file(body_len=5000, version=(1, 1, 0, 7))
    result, stages = run(sim, path)

    assert result.success, result.message
    assert result.previous_version == ImageVersion(1, 0, 0, 0)
    assert result.running_version == ImageVersion(1, 1, 0, 7)
    assert result.confirmed
    assert sim.boot_count == 1
    with open(path, "rb") as f:
        assert bytes(sim.buf) == f.read()
    for stage in (fw_update.STAGE_PREPARE, fw_update.STAGE_SEND, fw_update.STAGE_VERIFY,
                  fw_update.STAGE_REBOOT, fw_update.STAGE_RECONNECT, fw_update.STAGE_CONFIRM):
        assert stage in stages


def test_permanent_install(image_file):
    sim = SimDevice()
    result, _ = run(sim, image_file(version=(2, 0, 0, 0)), permanent=True)
    assert result.success
    assert sim.apply_mode == 1
    assert sim.info_polls == 1      # already confirmed, no waiting


def test_downgrade_is_allowed(image_file):
    sim = SimDevice(running=(3, 0, 0, 0))
    result, _ = run(sim, image_file(version=(2, 9, 0, 0)))
    assert result.success
    assert result.running_version == ImageVersion(2, 9, 0, 0)


def test_no_wait_returns_after_reboot(image_file):
    sim = SimDevice()
    result, stages = run(sim, image_file(), wait=False)
    assert result.success
    assert fw_update.STAGE_RECONNECT not in stages
    assert result.running_version is None


def test_chunk_size_rounded_to_write_alignment(image_file):
    sim = SimDevice(max_chunk=100, write_align=16)
    result, _ = run(sim, image_file(body_len=3000))
    assert result.success
    assert sim.writes == -(-sim.size // 96)


def test_leftover_session_is_aborted_first(image_file):
    sim = SimDevice()
    sim.state = FwState.RECEIVING
    result, _ = run(sim, image_file())
    assert result.success
    assert sim.aborts == 1


# ------------------------------------------------------------ transport hiccups


def test_transient_error_retries_chunk(image_file):
    sim = SimDevice()
    sim.transient_failures = {512: 1}
    result, _ = run(sim, image_file(body_len=3000))
    assert result.success


def test_retry_of_delivered_chunk_counts_as_sent(image_file):
    sim = SimDevice()
    sim.drop_after_write = {1024}
    result, _ = run(sim, image_file(body_len=3000))
    assert result.success
    assert bytes(sim.buf) == mcuboot_image(body_len=3000)


def test_device_vanishing_mid_transfer_is_a_transport_error(image_file):
    # A disconnect can surface as a stalled request; with FW_STATUS then
    # unreadable too, that must not be mistaken for "not supported".
    sim = SimDevice()
    sim.vanish_at = 1024
    with pytest.raises(RecomDeviceException.TransportException, match="stopped responding"):
        run(sim, image_file(body_len=3000))


def test_persistent_transport_error_propagates(image_file):
    sim = SimDevice()
    sim.transient_failures = {0: 10}
    with pytest.raises(RecomDeviceException.TransportException):
        run(sim, image_file())


# ------------------------------------------------------------ refusals and failures


def test_old_protocol_version_not_supported(image_file):
    sim = SimDevice(protocol_version=1)
    with pytest.raises(RecomDeviceException.FwUpdateNotSupported):
        run(sim, image_file())


def test_device_without_fw_update_support(image_file):
    sim = SimDevice()
    sim.supports_fw = False
    with pytest.raises(RecomDeviceException.FwUpdateNotSupported):
        run(sim, image_file())


def test_image_larger_than_device_accepts(image_file):
    sim = SimDevice(max_image=1024)
    with pytest.raises(fw_update.FwUpdateFailed, match="at most 1024"):
        run(sim, image_file(body_len=4000))
    assert sim.state == FwState.IDLE


def test_unsigned_file_rejected_before_sending(tmp_path):
    path = tmp_path / "raw.bin"
    path.write_bytes(b"\x00" * 2048)
    sim = SimDevice()
    with pytest.raises(ImageError):
        run(sim, str(path))
    assert sim.writes == 0


def test_opaque_format_sends_any_file(tmp_path):
    path = tmp_path / "raw.bin"
    path.write_bytes(b"\x01" * 2000)
    sim = SimDevice(image_format=0)
    result, _ = run(sim, str(path), wait=False)
    assert result.success
    assert bytes(sim.buf) == b"\x01" * 2000


def test_begin_refused_while_previous_update_unconfirmed(image_file):
    sim = SimDevice(confirmed=False)
    with pytest.raises(fw_update.FwUpdateFailed, match="not yet confirmed"):
        run(sim, image_file())
    assert sim.last_result == FwResult.ERR_UNCONFIRMED


def test_device_side_verification_failure(image_file):
    sim = SimDevice()
    sim.verify_error = FwResult.ERR_BAD_IMAGE
    with pytest.raises(fw_update.FwUpdateFailed, match="verify.*rejected"):
        run(sim, image_file())
    assert sim.boot_count == 0


def test_bootloader_rejects_image(image_file):
    sim = SimDevice(running=(1, 0, 0, 0))
    sim.bootloader_rejects = True
    result, _ = run(sim, image_file(version=(1, 1, 0, 0)))
    assert not result.success
    assert "previous firmware" in result.message
    assert result.running_version == ImageVersion(1, 0, 0, 0)


def test_device_never_confirms(image_file):
    sim = SimDevice()
    sim.never_confirms = True
    result, _ = run(sim, image_file(), confirm_timeout=0.2)
    assert not result.success
    assert "did not confirm" in result.message
    assert result.running_version == ImageVersion(1, 2, 3, 4)


def test_device_does_not_come_back(image_file):
    sim = SimDevice()
    sim.comes_back = False
    with pytest.raises(fw_update.FwUpdateFailed, match="did not come back"):
        run(sim, image_file(), reboot_timeout=0.1)
