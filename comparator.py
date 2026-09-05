"""
comparator.py – Hash-basierter Verzeichnisvergleich
=====================================================

Dieses Modul vergleicht Quelldateien gegen einen Hash-Index des Zielverzeichnisses.
Der Vergleich ist hash-basiert und pfad-unabhängig: Eine Datei gilt als gesichert,
wenn ihr SHA-256-Hash irgendwo im Zielverzeichnis gefunden wird.

Die Dateien werden in vier Kategorien eingeteilt:

1. IDENTICAL    – Hash UND relativer Pfad stimmen überein (perfektes Backup)
2. MOVED        – Hash gefunden, aber unter anderem Pfad (Backup existiert, aber verschoben)
3. NO_BACKUP    – Hash nirgends im Ziel gefunden (kein Backup vorhanden)
4. DUPLICATES   – Dateien, die mehrfach im Ziel existieren (Aufräum-Kandidaten)

Verwendung:
    from comparator import compare_directories, ComparisonResult

    result = compare_directories(source_files, target_files, target_index,
                                  source_root, target_root)
    print(f"Identisch: {len(result.identical)}")
    print(f"Verschoben: {len(result.moved)}")
    print(f"Kein Backup: {len(result.no_backup)}")
    print(f"Duplikate im Ziel: {len(result.duplicates)}")

Autor: BackUpRunner
"""

from dataclasses import dataclass, field
from enum import Enum
from scanner import FileInfo


class FileStatus(Enum):
    """
    Status einer Quelldatei nach dem Vergleich mit dem Zielverzeichnis.

    IDENTICAL:  Hash UND relativer Pfad stimmen überein.
                → Perfektes Backup, Datei ist identisch am gleichen Ort.

    MOVED:      Hash im Ziel gefunden, aber an anderer Stelle.
                → Datei ist gesichert, liegt aber in einem anderen Ordner.

    NO_BACKUP:  Hash existiert nirgends im Ziel.
                → Diese Datei hat kein Backup und muss noch gesichert werden.
    """
    IDENTICAL = "identical"
    MOVED = "moved"
    NO_BACKUP = "no_backup"


@dataclass
class ComparedFile:
    """
    Ergebnis des Vergleichs einer einzelnen Quelldatei.

    Attributes:
        source_file:    FileInfo der Quelldatei
        status:         Vergleichsstatus (IDENTICAL, MOVED, NO_BACKUP)
        target_paths:   Liste der Fundorte im Ziel (leer bei NO_BACKUP).
                        Bei IDENTICAL enthält sie den identischen Pfad.
                        Bei MOVED enthält sie alle Fundorte mit gleichem Hash.
    """
    source_file: FileInfo
    status: FileStatus
    target_paths: list[str] = field(default_factory=list)


@dataclass
class DuplicateGroup:
    """
    Eine Gruppe von Dateien im Ziel, die den gleichen Hash haben.

    Wird verwendet, um Duplikate im Backup zu identifizieren –
    Dateien, die mehrfach vorhanden sind und aufgeräumt werden könnten.

    Attributes:
        hash:       SHA-256 Hash, der bei allen Dateien identisch ist
        size:       Dateigröße in Bytes (identisch für alle Duplikate)
        paths:      Liste aller Pfade im Ziel mit diesem Hash
    """
    hash: str
    size: int
    paths: list[str]


@dataclass
class ComparisonResult:
    """
    Gesamtergebnis eines Verzeichnisvergleichs.

    Enthält alle verglichenen Dateien, aufgeteilt in Kategorien,
    sowie die gefundenen Duplikate im Ziel.

    Attributes:
        identical:      Dateien mit identischem Hash UND Pfad
        moved:          Dateien mit identischem Hash, aber anderem Pfad
        no_backup:      Dateien ohne Backup im Ziel
        duplicates:     Gruppen von Duplikaten im Zielverzeichnis
        source_root:    Wurzelverzeichnis der Quelle
        target_root:    Wurzelverzeichnis des Ziels
        source_count:   Gesamtanzahl gescannter Quelldateien
        target_count:   Gesamtanzahl gescannter Zieldateien
    """
    identical: list[ComparedFile] = field(default_factory=list)
    moved: list[ComparedFile] = field(default_factory=list)
    no_backup: list[ComparedFile] = field(default_factory=list)
    duplicates: list[DuplicateGroup] = field(default_factory=list)
    source_root: str = ""
    target_root: str = ""
    source_count: int = 0
    target_count: int = 0


def compare_directories(
    source_files: list[FileInfo],
    target_files: list[FileInfo],
    target_index: dict[str, list[str]],
    source_root: str,
    target_root: str
) -> ComparisonResult:
    """
    Vergleicht Quelldateien gegen den Hash-Index des Zielverzeichnisses.

    Für jede Quelldatei wird geprüft:
    1. Existiert der SHA-256-Hash irgendwo im Zielverzeichnis?
    2. Falls ja: Stimmt auch der relative Pfad überein?

    Zusätzlich werden Duplikate im Ziel erkannt (gleicher Hash, mehrere Pfade).

    Der Vergleich des relativen Pfads funktioniert so:
    - Quelldatei: /Volumes/USB/Projekte/Web/index.html → relativ: Web/index.html
    - Zieldatei:  /Volumes/NAS/Backup/Web/index.html   → relativ: Web/index.html
    - → IDENTICAL (gleicher Hash + gleicher relativer Pfad)

    Wenn die gleiche Datei unter /Volumes/NAS/Archiv/alt/index.html liegt:
    - → MOVED (gleicher Hash, aber anderer relativer Pfad)

    Args:
        source_files:   Liste der gescannten Quelldateien
        target_files:   Liste der gescannten Zieldateien
        target_index:   Hash-Index des Ziels (aus build_hash_index())
        source_root:    Wurzelverzeichnis der Quelle
        target_root:    Wurzelverzeichnis des Ziels

    Returns:
        ComparisonResult mit allen kategorisierten Dateien und Duplikaten
    """
    result = ComparisonResult(
        source_root=source_root,
        target_root=target_root,
        source_count=len(source_files),
        target_count=len(target_files)
    )

    # ── Schritt 1: Relative-Pfad-Index für das Ziel aufbauen ──
    # Ermöglicht schnelles Prüfen, ob eine Datei am gleichen relativen Pfad existiert.
    # Key: relativer Pfad, Value: Hash der Zieldatei
    target_relpath_to_hash: dict[str, str] = {}
    for target_file in target_files:
        target_relpath_to_hash[target_file.relative_path] = target_file.hash

    # ── Schritt 2: Jede Quelldatei gegen das Ziel vergleichen ──
    for source_file in source_files:
        source_hash = source_file.hash
        source_relpath = source_file.relative_path

        if source_hash in target_index:
            # Hash wurde im Ziel gefunden → Datei ist gesichert
            target_paths = target_index[source_hash]

            # Prüfen ob der relative Pfad übereinstimmt
            # (d.h. die Datei liegt im Ziel an der gleichen Stelle)
            target_hash_at_same_path = target_relpath_to_hash.get(source_relpath)

            if target_hash_at_same_path == source_hash:
                # Hash UND Pfad stimmen überein → perfektes Backup
                result.identical.append(ComparedFile(
                    source_file=source_file,
                    status=FileStatus.IDENTICAL,
                    target_paths=target_paths
                ))
            else:
                # Hash gefunden, aber an anderer Stelle → verschoben/umbenannt
                result.moved.append(ComparedFile(
                    source_file=source_file,
                    status=FileStatus.MOVED,
                    target_paths=target_paths
                ))
        else:
            # Hash nicht gefunden → kein Backup vorhanden
            result.no_backup.append(ComparedFile(
                source_file=source_file,
                status=FileStatus.NO_BACKUP,
                target_paths=[]
            ))

    # ── Schritt 3: Duplikate im Ziel finden ──
    # Alle Hashes, die im Ziel mehr als einmal vorkommen, sind Duplikate.
    # Diese könnten aufgeräumt werden, um Speicherplatz zu sparen.
    for hash_value, paths in target_index.items():
        if len(paths) > 1:
            # Dateigröße ermitteln (alle Duplikate haben die gleiche Größe)
            size = 0
            for target_file in target_files:
                if target_file.hash == hash_value:
                    size = target_file.size
                    break

            result.duplicates.append(DuplicateGroup(
                hash=hash_value,
                size=size,
                paths=paths
            ))

    return result
