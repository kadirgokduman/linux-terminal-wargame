from __future__ import annotations

import base64
import io
import shutil
import tarfile
from pathlib import Path

import pytest
import yaml

from wargame.flags import derive_flag
from wargame.model import (
    LevelError,
    build_context,
    iter_member_texts,
    load_all,
    load_level,
    render,
    template_variables,
)
from wargame.pcap import build_capture
from wargame.provision import Provisioner

SECRET = b"\x11" * 32
EPOCH = "test"


@pytest.fixture(scope="module")
def levels(levels_dir: Path):
    return load_all(levels_dir)


def flag_for(level_id: str) -> str:
    return derive_flag(SECRET, level_id, EPOCH)


def rendered(level) -> dict[str, str]:
    """Seviyenin ürettiği tüm statik metinler (arşiv üyeleri dahil)."""
    context = build_context(level, flag_for)
    out = {}
    for spec in level.files:
        if spec.template:
            text = (level.root / spec.template).read_text(encoding="utf-8")
            out[spec.path] = render(text, context, where=spec.path)
        elif spec.content is not None:
            out[spec.path] = render(spec.content, context, where=spec.path)
    for spec in level.archives:
        for name, text in iter_member_texts(level, spec.members):
            out[f"{spec.path}:{name}"] = render(text, context, where=name)
    return out


def test_ids_are_contiguous(levels):
    assert [lv.id for lv in levels] == [
        "00", "01", "02", "03", "04", "05",
        "06", "07", "08", "09", "10", "11",
    ]


def test_requires_chain(levels):
    assert levels[0].requires is None
    for previous, level in zip(levels, levels[1:]):
        assert level.requires == previous.id


def test_flag_targets_next_level(levels):
    for level in levels:
        assert level.flag_path == f"/etc/wargame/pass/{level.id}"
        assert level.next_id == f"{int(level.id) + 1:02d}"


def test_flag_files_are_private(levels):
    for level in levels:
        assert level.flag_mode == 0o400
        assert level.flag_owner == level.user


def test_every_level_has_docs_and_hints(levels, repo_root: Path):
    for level in levels:
        assert level.docs, f"{level.id}: docs alanı boş"
        assert (repo_root / level.docs).is_file(), f"{level.id}: {level.docs} yok"
        assert len(level.hints) >= 2, f"{level.id}: en az 2 ipucu kademesi"


def test_level_only_exposes_its_own_next_flag(levels):
    """Bir seviye yalnızca bir sonraki mührü açığa çıkarabilir."""
    for level in levels:
        for spec in level.files:
            text = (
                (level.root / spec.template).read_text(encoding="utf-8")
                if spec.template
                else (spec.content or "")
            )
            for variable in template_variables(text):
                if variable.startswith("flag"):
                    target = variable.split(":", 1)[1] if ":" in variable else level.next_id
                    assert target.zfill(2) == level.next_id, (
                        f"{level.id}/{spec.path}: yalnızca {level.next_id} açığa "
                        f"çıkarılabilir, {target} değil"
                    )


def test_home_files_belong_to_level_user(levels):
    for level in levels:
        for spec in level.files:
            if not spec.path.startswith("/home/"):
                continue
            if spec.mode & 0o4000:  # SUID bilinçli istisna
                continue
            assert spec.owner == level.user, (
                f"{level.id}: {spec.path} sahibi {spec.owner}, beklenen {level.user}"
            )


def test_level_00_hands_out_flag_01(levels):
    body = rendered(levels[0])["/home/player00/welcome.txt"]
    assert flag_for("01") in body


def test_level_01_encodes_flag_02(levels):
    files = rendered(levels[1])
    ledger = [text for path, text in files.items() if "/ledger/" in path]
    encoded = base64.b64encode(flag_for("02").encode()).decode()
    assert any(encoded in text for text in ledger)
    assert not any(flag_for("02") in text for text in files.values()), (
        "mühür düz metin olarak sızmamalı"
    )


def test_level_02_uses_setuid_reader(levels):
    level = levels[2]
    suid = [f for f in level.files if f.mode & 0o4000]
    assert len(suid) == 1
    assert suid[0].owner == "player03"
    assert suid[0].mode == 0o4755
    assert suid[0].source == "/opt/wargame/bin/reader"


def test_templates_render_without_unknown_variables(levels):
    for level in levels:
        rendered(level)  # bilinmeyen değişken LevelError fırlatır


def test_no_level_leaks_a_future_flag(levels):
    """Statik içerik yalnızca kendi bir sonraki mührünü taşıyabilir."""
    secrets = {level.id: flag_for(level.id) for level in levels}
    for level in levels:
        for path, text in rendered(level).items():
            for owner_id, value in secrets.items():
                if value in text:
                    assert owner_id == level.next_id, (
                        f"{level.id}:{path} mühür {owner_id} değerini taşıyor"
                    )


def test_each_seal_is_reachable_from_the_previous_level(levels):
    """Her mühür, bir önceki seviyeden erişilebilir olmalı.

    Erişim statik olabilir (dosya içinde) ya da çalışma zamanında
    kurulabilir (SUID okuyucu, cron çıktısı). İkisi de kabul; hiçbiri yoksa
    zincir kopmuştur.
    """
    for level in levels[1:]:
        previous = levels[int(level.id) - 1]
        body = "\n".join(rendered(previous).values())
        value = flag_for(level.id)
        encodings = [value, base64.b64encode(value.encode()).decode(), value.encode().hex()]
        static = any(encoded in body for encoded in encodings)
        runtime = (
            any(spec.source for spec in previous.files)
            or bool(previous.cron)
            or bool(previous.pcaps)
            or any(path.startswith("/etc/sudoers.d/")
                   for path in previous.file_paths())
        )
        assert static or runtime, (
            f"mühür {level.id} bir önceki seviyeden erişilemiyor"
        )


def test_fixed_width_records(levels):
    """Seviye 03'ün kasa kayıtları tam 4096 bayt olmalı (find -size 4096c)."""
    level = next(lv for lv in levels if lv.id == "03")
    padded = [f for f in level.files if f.pad_to]
    assert padded, "seviye 03 en az bir pad_to dosyası içermeli"
    context = build_context(level, flag_for)
    target = next(f for f in level.files if f.owner == "player03")
    body = render(
        (level.root / target.template).read_text(encoding="utf-8"),
        context,
    ).encode("utf-8")
    assert len(body) <= target.pad_to
    assert len(body.ljust(target.pad_to, b"\n")) == 4096

    siblings = [f for f in level.files if f is not target and f.pad_to == 4096]
    assert siblings, "aynı boyutta ama başka sahipte bir tuzak dosya olmalı"


def test_level_04_has_exactly_one_sealed_custodian_line(levels):
    level = next(lv for lv in levels if lv.id == "04")
    log = rendered(level)["/home/player04/logs/1996-transfer.log"]
    hits = [
        line for line in log.splitlines()
        if "actor=custodian" in line and "status=sealed" in line
    ]
    assert len(hits) == 1, f"tek eşleşme bekleniyordu, {len(hits)} bulundu"
    assert flag_for("05") in hits[0]


def test_level_06_builds_nested_archives(levels):
    level = next(lv for lv in levels if lv.id == "06")
    assert len(level.archives) == 1
    spec = level.archives[0]
    assert spec.fmt == "tar.gz"
    nested = [m for m in spec.members if m.members]
    assert len(nested) == 1 and nested[0].fmt == "tar.bz2"
    assert nested[0].name.endswith(".tar.bz2")

    provisioner = Provisioner(levels, SECRET, EPOCH, dry_run=True, quiet=True)
    context = build_context(level, flag_for)
    data = provisioner._build_archive(level, spec.members, spec.fmt, context, spec.path)

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as outer:
        names = outer.getnames()
        assert "MANIFEST" in names
        assert nested[0].name in names
        inner = outer.extractfile(nested[0].name).read()

    with tarfile.open(fileobj=io.BytesIO(inner), mode="r:bz2") as inner_tar:
        body = inner_tar.extractfile("seal.txt").read().decode()
    assert flag_for("07") in body


def test_archive_bytes_are_deterministic(levels):
    """Aynı girdi aynı arşiv baytlarını üretmeli (idempotent materyalizasyon)."""
    level = next(lv for lv in levels if lv.id == "06")
    spec = level.archives[0]
    provisioner = Provisioner(levels, SECRET, EPOCH, dry_run=True, quiet=True)
    context = build_context(level, flag_for)
    first = provisioner._build_archive(level, spec.members, spec.fmt, context, spec.path)
    second = provisioner._build_archive(level, spec.members, spec.fmt, context, spec.path)
    assert first == second


def test_level_07_serves_only_on_loopback(levels):
    level = next(lv for lv in levels if lv.id == "07")
    script = rendered(level)["/usr/local/lib/wargame/serve-08"]

    assert '"127.0.0.1", 8080' in script, "servis yalnızca loopback'e bağlanmalı"
    assert "/etc/wargame/pass/08" in script, "mührü çalışma anında okumalı"
    assert flag_for("08") not in script, "betik mühür değerini taşımamalı"

    job = next(spec for spec in level.cron if spec.schedule == "@reboot")
    assert job.user == "player08", "servis, mührün sahibi adına çalışmalı"


def test_level_08_keeps_seal_in_environment(levels):
    level = next(lv for lv in levels if lv.id == "08")
    script = rendered(level)["/usr/local/lib/wargame/hold-09"]

    assert "/etc/wargame/pass/09" in script
    assert flag_for("09") not in script, "betik mühür değerini taşımamalı"
    assert "env ARCHIVE_SEAL=" in script, "mühür ortam değişkenine konmalı"
    assert "--reuid=player08" in script, "süreç oyuncunun kimliğinde olmalı"

    job = next(spec for spec in level.cron if spec.schedule == "@reboot")
    assert job.user == "root", "mühür odasını yalnızca root okuyabilir"


def test_level_02_has_acl_fallback_for_hardened_profile(levels):
    """no_new_privs altında SUID/setcap çalışmadığı için izin ACL'de."""
    level = next(lv for lv in levels if lv.id == "02")
    assert len(level.acls) == 1
    acl = level.acls[0]
    assert acl.path == "/etc/wargame/pass/03"
    assert acl.user == "player02"
    assert acl.perms == "r"
    assert acl.when == "suid-disabled", "varsayılan profilde ACL uygulanmamalı"


def test_level_09_sudo_rule_is_narrow(levels):
    level = next(lv for lv in levels if lv.id == "09")
    rule = next(f for f in level.files if f.path == "/etc/sudoers.d/wargame-09")
    assert rule.owner == "root"
    assert rule.mode == 0o440, "sudo, grup/dünya tarafından yazılabilir dosyayı reddeder"
    assert rule.when == "suid-enabled", "NNP altında kural işlevsiz; yayınlanmamalı"

    body = rendered(level)[rule.path]
    assert "player09 ALL=(player10) NOPASSWD: /usr/bin/find" in body
    assert "ALL=(ALL" not in body, "kural root'a genişlememeli"
    assert "NOPASSWD: ALL" not in body


def test_level_09_has_hardened_fallback(levels):
    """NNP altında sudo imkânsız: ayrıcalıklı iş + kullanıcı betiği."""
    level = next(lv for lv in levels if lv.id == "09")
    fallback = [f for f in level.files if f.when == "suid-disabled"]
    paths = {f.path: f for f in fallback}

    script = paths["/var/spool/wargame/09/sync.sh"]
    assert script.owner == "player09", "betik oyuncuya ait ve yazılabilir olmalı"
    assert script.mode == 0o755

    wrapper = paths["/usr/local/lib/wargame/delegate-10"]
    assert wrapper.owner == "root"
    assert "--reuid=player10" in rendered(level)[wrapper.path]

    gated_cron = [spec for spec in level.cron if spec.when == "suid-disabled"]
    assert len(gated_cron) == 2, "@reboot + dakikalık tik"
    assert all(spec.user == "root" for spec in gated_cron)


def test_level_10_pcap_carries_the_seal(levels):
    level = next(lv for lv in levels if lv.id == "10")
    assert len(level.pcaps) == 1
    spec = level.pcaps[0]
    assert spec.mode == 0o640

    seal = render(spec.seal, build_context(level, flag_for))
    data = build_capture(spec.host, seal)

    assert data[:4] == b"\xd4\xc3\xb2\xa1", "klasik libpcap sihirli sayısı"
    assert seal.encode() in data, "mühür paket yükünde olmalı"
    assert b"X-Archive-Seal: " in data
    assert data.count(b"HTTP/1.1") == 8, "4 istek + 4 yanıt"


def test_pcap_is_deterministic(levels):
    level = next(lv for lv in levels if lv.id == "10")
    seal = flag_for("11")
    assert build_capture(level.pcaps[0].host, seal) == build_capture(level.pcaps[0].host, seal)


def test_level_11_hides_the_seal_with_xor(levels):
    level = next(lv for lv in levels if lv.id == "11")
    blob = next(f for f in level.files if f.path.endswith("/blob"))
    assert blob.encoding == "xor"

    plain = render(
        (level.root / blob.template).read_text(encoding="utf-8"),
        build_context(level, flag_for),
    )
    assert flag_for("12") in plain

    encoded = bytes(byte ^ 0x5A for byte in plain.encode())
    assert flag_for("12").encode() not in encoded, "diskte düz metin kalmamalı"
    assert bytes(byte ^ 0x5A for byte in encoded).decode().strip() == flag_for("12")

    checker = next(f for f in level.files if f.path.endswith("/checker"))
    assert checker.source == "/opt/wargame/bin/checker"
    assert checker.mode == 0o755


def test_level_05_runs_a_scheduled_job(levels):
    level = next(lv for lv in levels if lv.id == "05")
    assert any(spec.schedule == "@reboot" for spec in level.cron), (
        "@reboot işi olmadan çıktı ancak bir dakika sonra oluşur"
    )
    assert level.expose == ["/var/spool/wargame/05/seal.log"]

    # İş betiği mührü taşımamalı: yalnızca sahibinin izniyle okumalı.
    script = rendered(level)["/usr/local/lib/wargame/emit-06"]
    assert flag_for("06") not in script
    assert "/etc/wargame/pass/06" in script


# -- geçersiz tanımlar reddedilmeli ----------------------------------------


def _copy_level(levels_dir: Path, tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    shutil.copytree(levels_dir / "00-bootstrap", target)
    return target


def test_id_must_match_directory(levels_dir, tmp_path):
    target = _copy_level(levels_dir, tmp_path, "00-bootstrap")
    manifest = yaml.safe_load((target / "level.yml").read_text(encoding="utf-8"))
    manifest["id"] = "07"
    (target / "level.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    with pytest.raises(LevelError):
        load_level(target)


def test_requires_cannot_skip_a_level(levels_dir, tmp_path):
    target = _copy_level(levels_dir, tmp_path, "00-bootstrap")
    manifest = yaml.safe_load((target / "level.yml").read_text(encoding="utf-8"))
    manifest["requires"] = "00"
    (target / "level.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    with pytest.raises(LevelError):
        load_level(target)


def test_path_cannot_escape(levels_dir, tmp_path):
    target = _copy_level(levels_dir, tmp_path, "00-bootstrap")
    manifest = yaml.safe_load((target / "level.yml").read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = "/home/player00/../../etc/shadow"
    (target / "level.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    with pytest.raises(LevelError):
        load_level(target)


def test_unknown_template_variable_is_rejected():
    with pytest.raises(LevelError):
        render("{{flag:99}}", {"flag": "x"}, where="test")


def test_bad_filter_is_rejected():
    with pytest.raises(LevelError):
        render("{{flag|rot13}}", {"flag": "x"}, where="test")
