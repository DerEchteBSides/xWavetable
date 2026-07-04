# xWavetable

Eine kleine Desktop-App (Python/Tkinter), die einen Ordner rekursiv nach
`.wav`/`.xwt`-Dateien durchsucht, automatisch erkennt ob es sich um eine
**Single Cycle Waveform** oder ein **Wavetable** handelt, und das Ergebnis
wahlweise in zwei Formaten in einen Outputordner schreibt:

1. **`.xwt`** (Serum/Xfer-Stil) — behält die Ordnerstruktur des Inputs bei
2. **`.wav` + `format.json`** (MPC OS 3.9 Oscillator-Format) — flach, mit
   automatischer Geometrie-Gruppierung, exakt nach den Vorgaben aus
   [dreyandersson.com/blog/load-your-own-wavetables-mpc-3-9](https://dreyandersson.com/blog/load-your-own-wavetables-mpc-3-9/)

Beide Exports lassen sich in der GUI per Checkbox unabhängig ein-/ausschalten.

## Format 1: .xwt (Serum-Stil)

Technisch ein ganz normales RIFF/WAVE-File, 16-bit, mono, 44100 Hz:

- **Single Cycle**: `data`-Chunk enthält genau eine Waveform-Periode
  (Standard: 2048 Samples), kein `clm`-Chunk.
- **Wavetable**: `data`-Chunk enthält N Frames á 2048 Samples hintereinander,
  zusätzlich ein `clm`-Chunk mit dem Inhalt
  `<!>2048 00000000 wavetable (www.xferrecords.com)`.

```
Outputordner/
├── SingleCycles/<gleiche Unterordner wie Input>/<Name>.xwt
└── Wavetables/<gleiche Unterordner wie Input>/<Name>.xwt
```

## Format 2: MPC OS 3.9 Oscillator-Format

Die MPC stellt **strikte** Anforderungen an Wavetables (siehe verlinkter
Artikel) — eine davon falsch, und der Ordner wird kommentarlos ignoriert:

- Datei muss `.wav` heißen (kein `.xwt`), mono, 16/24/32-bit,
  Samplerate 22.050–96.000 Hz
- Dateilänge muss **exakt** `samples_per_cycle × num_cycles` sein
- Alle `.wav`-Dateien + ein `format.json` liegen **flach** in einem
  Bibliotheksordner — **keine** Unterordner
- **Eine** Geometrie pro Ordner (alle Tabellen darin gleich viele
  Samples/Cycle und gleich viele Cycles), definiert über `format.json`:
  ```json
  {
      "formatInfo": {
          "numSamplesPerSingleCycle": 2048,
          "numSingleCycles": 256
      }
  }
  ```
- Samples/Cycle: 512–16.384, Cycles: 2–2.048, max. 512 Dateien pro Ordner

Die App übernimmt das automatisch:

```
Outputordner/
└── Oscillators/
    ├── Wavetables/<Library>/*.wav + format.json
    └── SingleCycles/<Library>/*.wav
```

- Jeder Inputunterordner wird zu einem flachen `<Library>`-Ordner
  (verschachtelte Pfade werden mit " - " zusammengefügt, z. B.
  `Massive X - Remastered`).
- Enthält ein Inputordner **mehrere unterschiedliche Geometrien**
  (z. B. manche Tabellen mit 128, andere mit 256 Frames), legt die App
  automatisch getrennte Bibliotheksordner pro Geometrie an
  (`<Library> (2048x128)`, `<Library> (2048x256)`, …), jeweils mit
  eigenem `format.json`.
- Über 512 Dateien in einer Bibliothek werden automatisch in
  `<Library> Part1`, `<Library> Part2`, … aufgeteilt.
- Liegt die Frame-Größe oder Cycle-Anzahl außerhalb der MPC-Grenzen, gibt
  es eine Warnung im Log (die Datei wird trotzdem geschrieben).

**Installation auf der MPC:** Kopiere den kompletten Inhalt von
`Outputordner/Oscillators/` an die Wurzel eines USB-Sticks, einer SD-Karte
oder der internen SSD, z. B. `<Drive>/Oscillators/Wavetables/...`. Danach
auf der MPC: Preferences → Activations → *Get Oscillator Content* (einmalig),
dann im Track Edit unter Samples/Oscs → Layer-Source auf OSC stellen → im
Oscillator-Dropdown unter *User Wavetables* die Library auswählen.

## Installation

```bash
pip install -r requirements.txt
```

Unter Linux wird ggf. zusätzlich `python3-tk` benötigt:

```bash
sudo apt install python3-tk
```

Optional für Drag & Drop von Ordnern in die Inputliste:

```bash
pip install tkinterdnd2
```

(Ohne `tkinterdnd2` funktioniert die App genauso, nur eben ohne Drag & Drop —
Ordner lassen sich dann über den "＋ Hinzufügen"-Button auswählen.)

## Start

```bash
python3 xwavetable_app.py
```

## Mehrere Inputordner & flache Bibliotheksnamen

Über **"＋ Hinzufügen"** (oder per Drag & Drop, falls `tkinterdnd2`
installiert ist) lassen sich beliebig viele Inputordner zur Liste
hinzufügen. Jeder Inputordner wird zu einer eigenen Bibliotheksbasis,
benannt nach seinem Ordnernamen — Unterordner werden dabei flach an diesen
Namen angehängt (durch Leerzeichen getrennt), da weder die MPC noch das
`.xwt`-Format verschachtelte Bibliotheksordner unterstützen.

Beispiel: Input-Ordner `.../Serum` mit den Unterordnern `Basic` und
`Digital` ergibt zwei Bibliotheken **"Serum Basic"** und **"Serum
Digital"**; Dateien direkt im Ordner `Serum` (ohne Unterordner) landen in
der Bibliothek **"Serum"**. Ein zweiter hinzugefügter Inputordner, z. B.
`.../Massive`, erzeugt unabhängig davon eigene Bibliotheken mit dem
Präfix "Massive". Tragen zwei hinzugefügte Inputordner zufällig denselben
Namen, wird automatisch durchnummeriert (`Serum`, `Serum 2`, …).

Diese Logik gilt sowohl für den `.xwt`- als auch den MPC-Export.

## Bedienung

1. **Inputordner** über "＋ Hinzufügen" hinzufügen (mehrere möglich) —
   jeder wird rekursiv inkl. aller Unterordner durchsucht.
2. **Outputordner** wählen.
3. **Export**-Checkboxen: `.xwt` und/oder `.wav`+`format.json` (MPC) aktivieren.
4. Optional: **Frame-Größe / Resampling** anpassen (Standard: 2048
   Samples/Cycle, 0 = aus/Quell-Größe übernehmen — siehe unten).
5. Optional: **"Frames angleichen"** wählen (siehe unten: Aus / Zyklisch
   wiederholen / Linear interpolieren / Spektral interpolieren).
6. Optional: **Mindest-Frame-Anzahl** anpassen (Standard: 256, siehe unten).
7. Optional: **"Frames phasenausrichten"** aktivieren (siehe unten).
8. **Run** klicken.

Alle Einstellungen (Inputordner-Liste, Outputordner, Export-Auswahl,
Frame-Größe, Angleich-Modus, Mindest-Frame-Anzahl, Phasenausrichtung)
werden beim Klick auf Run sowie beim Schließen der App automatisch
gespeichert (`~/.xwavetable_settings.json`) und beim nächsten Start
wieder vorausgefüllt.

## Option: Frames pro Inputordner angleichen ("extend frames")

Enthält ein Inputunterordner mehrere Wavetables mit unterschiedlicher
Cycle-Anzahl (z. B. eines mit 64, ein anderes mit 256 Frames), würde die
App im MPC-Export normalerweise pro Geometrie einen eigenen Bibliotheks-
ordner anlegen (`Ordner (2048x64)`, `Ordner (2048x256)`, …) — das kann bei
vielen Quelldateien schnell unübersichtlich viele Ordner erzeugen.

Mit aktiviertem Angleich wird stattdessen für jeden Inputordner die
**größte vorkommende Frame-Anzahl** ermittelt, und alle kürzeren
Wavetables darauf verlängert. Zwei Methoden stehen zur Wahl:

- **Zyklisch wiederholen**: Der vorhandene Frame-Verlauf wird exakt
  wiederholt (z. B. ein 64-Frame-Table wird 4× hintereinander gehängt, um
  auf 256 Frames zu kommen). Der Cycle-Inhalt bleibt dabei 1:1 erhalten,
  nichts wird neu berechnet — dafür entsteht beim Durchscannen ein
  hörbarer "Sprung"/Loop-Punkt alle Original-Frame-Anzahl an Frames.
- **Linear interpolieren**: Zusätzliche Zwischenframes werden im
  **Zeitbereich** (Sample für Sample) zwischen den Original-Frames
  überblendet. Schnell und für ähnliche, phasenkonsistente Frames meist
  ausreichend — kann aber bei stark unterschiedlichen Frames (z. B. Sinus
  → Rechteck) oder phasenversetzten Cycles zu hörbaren Auslöschungen
  ("abgehacktes" Morphen) führen, da sich gegenphasige Anteile beim
  linearen Mischen teilweise aufheben.
- **Spektral interpolieren**: Interpoliert stattdessen Magnitude und
  Phase im **Frequenzbereich** (Magnitude linear, Phase entlang des
  kürzesten Winkelpfads) — genau das Prinzip hinter dem "Spectrum"-Morph-
  Modus aus Massive/Massive X. Dadurch bleibt die Klangenergie über den
  Übergang erhalten und es entstehen keine Auslöschungsartefakte. Klingt
  bei unterschiedlichen/phasenversetzten Frames spürbar sauberer als
  lineare Interpolation, ist aber etwas rechenintensiver (FFT pro Frame).

Beide Methoden funktionieren immer ohne Rest, weil alle Frame-Zahlen
bereits auf Zweierpotenzen gerundet werden (Ziel ist also immer ein
ganzzahliges Vielfaches der Quelle). Ergebnis: ein einziger, einheitlicher
Bibliotheksordner pro Inputordner statt mehrerer pro Geometrie.

Wavetables mit unterschiedlicher **Frame-Größe** (Samples/Cycle, nicht
Frame-Anzahl) werden davon nicht berührt und bleiben weiterhin getrennt,
da sich deren Cycle-Inhalte nicht sinnvoll angleichen lassen.

## Option: Frame-Größe / Resampling (Samples pro Cycle)

Wichtig zu wissen: Bringt eine Quelldatei bereits eine eigene Frame-Größe
mit (per `clm`-Chunk, z. B. weil sie selbst schon ein Serum-Wavetable mit
4096 statt 2048 Samples/Cycle ist), wurde diese **bisher immer
übernommen** — unabhängig von der eingestellten Frame-Größe. Das konnte
zu inkonsistenten Geometrien zwischen verschiedenen Quelldateien führen.

Analog zur Mindest-Frame-Anzahl gilt jetzt:

- **Wert ≠ 0** (Standard: **2048**): JEDE Datei wird auf diese Cycle-Länge
  resampelt/interpoliert — auch wenn die Quelle selbst schon eine andere
  Frame-Größe eingebettet hat. Die tatsächliche Cycle-**Anzahl** der
  Quelle bleibt dabei korrekt erhalten (z. B. 4 Original-Cycles à 4096
  Samples werden zu 4 Cycles à 2048 Samples — nicht zu 8 falsch
  "erratenen" Cycles). Sorgt für konsistente Geometrie über alle
  Inputdateien hinweg.
- **Wert = 0**: Resampling aus — die im `clm`-Chunk der Quelle
  eingebettete Frame-Größe wird wie bisher übernommen; ist keine
  vorhanden, wird die Standardgröße 2048 verwendet.

## Option: Mindest-Frame-Anzahl

Diese Option ist unabhängig vom Ordner-Angleich oben und wirkt **global**
auf jedes einzelne Wavetable, auch wenn innerhalb seines Ordners keine
unterschiedlichen Geometrien vorliegen.

Hat ein Wavetable weniger Frames als die eingestellte Mindest-Anzahl
(Standard: **256**, auf 2er-Potenz gerundet), wird es mit der oben
gewählten Methode (Zyklisch/Linear/Spektral) auf diese Mindest-Größe
hochgerechnet. Auf `0` gesetzt ist die Option deaktiviert. Wirkt nur,
wenn "Frames angleichen" oben nicht auf "Aus" steht.

Mehr Frames fügen keine neue Klanginformation hinzu — sie sorgen aber für
zwei konkrete Verbesserungen:

- Geräte/Engines, die beim Morphen nicht selbst weich interpolieren,
  sondern frameweise springen (wie wir es bei der MPC beobachtet haben),
  bekommen dadurch deutlich feinere, weniger hörbare Morph-Schritte.
- Da benachbarte, vorab interpolierte Frames sich kaum noch unterscheiden,
  hat die geräteeigene Interpolation (die ja möglicherweise selbst nur
  einfach im Zeitbereich arbeitet) kaum noch Spielraum für Auslöschungs-
  artefakte — das Morphen wird also auch dann sauberer, wenn das
  Zielgerät selbst keine gute Interpolation beherrscht.

`256` ist kein Zufallswert: Laut dem MPC-Dokumentationsartikel ist das
exakt die Serum-Standardgröße (256 Frames × 2048 Samples), auf die viele
Tools/Geräte ausgelegt sind.

**Trade-off:** Die Dateigröße steigt proportional zur Frame-Anzahl (z. B.
16 → 256 Frames bedeutet 16× größere Dateien). Bei Wavetables, deren
Original-Frames sich kaum unterscheiden, bringt eine hohe Mindest-Anzahl
keinen hörbaren Vorteil, nur unnötig große Dateien.

## Option: Frames phasenausrichten

Diese Option ist **unabhängig** vom Frame-Angleich oben und wirkt auf
**alle** Wavetables, auch wenn keine Frame-Anzahl-Anpassung nötig ist.

Manche Wavetables (insbesondere aus Massive/Massive X extrahierte) haben
Original-Frames, deren Wellenform-Cycles bei unterschiedlichen Phasenlagen
"geschnitten" wurden. Scannt ein Synth beim Abspielen durch solche
benachbarten Frames, entstehen dadurch hörbare Sprünge/Klicks — unabhängig
davon, ob er dabei linear oder spektral interpoliert, denn das Problem
steckt schon in den gespeicherten Original-Frames selbst.

Mit aktivierter Phasenausrichtung wird jeder Frame per Kreuzkorrelation
(FFT-basiert) zirkulär so verschoben, dass er bestmöglich zum vorherigen
Frame passt — es wird **nichts** resampelt oder inhaltlich verändert,
nur die Startposition jedes Cycles wird angepasst. Das reduziert
Phasensprünge zwischen benachbarten Frames spürbar und macht das Morphen
beim Abspielen auf jedem Synth/Hardware-Oszillator sauberer.

## Erkennungslogik

Pro Datei wird die Gesamtanzahl an Samples durch die Frame-Größe geteilt:

- **Weniger als 2 Frames** → Single Cycle Waveform; wird sauber (per
  periodischer linearer Interpolation, damit der Loop nahtlos bleibt)
  auf genau eine Frame-Länge resampelt.
- **2 oder mehr Frames** → Wavetable. Die Cycle-Anzahl wird dabei auf die
  **nächstliegende Zweierpotenz** gerundet (z. B. 64/128/256/512/1024) und
  dann jeder einzelne Frame separat auf die Ziel-Frame-Größe resampelt
  (statt das gesamte Wavetable global zu strecken), damit die einzelnen
  Cycles nicht ineinander verschmieren. Das Runden auf Zweierpotenzen ist
  wichtig für die MPC: deren Wavetable-Oscillator erkennt die im
  `clm`-Chunk eingebettete Geometrie (auch ganz ohne `format.json`)
  offenbar nur zuverlässig, wenn die Cycle-Anzahl eine Zweierpotenz ist —
  krumme Werte wie 249 oder 250 Cycles werden sonst stillschweigend
  ignoriert/abgelehnt.
- Enthält die Quelldatei bereits einen `clm`-Chunk mit eigener
  Frame-Größenangabe (z. B. weil sie selbst schon ein Serum-Wavetable ist),
  wird diese Frame-Größe automatisch übernommen statt der eingestellten
  Standardgröße.

Mehrkanal-Input wird automatisch auf mono heruntergemischt. Unterstützte
Eingangsformate: PCM 16/24/32-bit sowie IEEE-Float 32/64-bit (inkl.
`WAVE_FORMAT_EXTENSIBLE`-Container, wie sie z. B. manche kommerziellen
Sample-Libraries verwenden). Output ist immer 16-bit PCM, 44100 Hz, mono.

## Dateien

- `xwavetable_app.py` — die komplette App (GUI + Verarbeitungslogik)
- `requirements.txt` — Python-Abhängigkeiten (`numpy`, optional `tkinterdnd2`
  für Drag & Drop)

