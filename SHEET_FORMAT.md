# 📋 Google Sheet Format — Quiz Video Maker

> **Share this document with your client.** They fill the sheet, you get videos.

---

## Sheet Structure

The Google Sheet has **two tabs** (worksheets):

### Tab 1: `CONFIG`

| Column | Header       | Description                                | Example            |
|--------|--------------|--------------------------------------------|--------------------|
| A      | `BATCH`      | Batch number (1, 2, 3…) — one batch = one video | `1`           |
| B      | `LANGUAGE`   | Language code for TTS voice                | `fr`               |
| C      | `VOICE`      | *(Optional)* Gemini voice name             | `Kore`             |
| D      | `TITLE`      | Video title / filename                     | `English Quiz #1`  |
| E      | `STATUS`     | Leave blank — system fills this            | *(auto: DONE)*     |
| F      | `VIDEO_URL`  | Leave blank — system fills Drive link      | *(auto)*           |

**Example `CONFIG` tab:**

| BATCH | LANGUAGE | VOICE | TITLE                     | STATUS | VIDEO_URL |
|-------|----------|-------|---------------------------|--------|-----------|
| 1     | en       | Puck  | English Quiz - Beginners  |        |           |
| 2     | fr       | Kore  | Quiz Français - Niveau 1  |        |           |
| 3     | en       | Puck  | English Quiz - Advanced   |        |           |

---

### Tab 2: `QUESTIONS`

| Column | Header       | Description                                          | Example                                      |
|--------|--------------|------------------------------------------------------|----------------------------------------------|
| A      | `BATCH`      | Which batch this question belongs to (matches CONFIG) | `1`                                          |
| B      | `#`          | Question number within the batch (1, 2, 3…)          | `1`                                          |
| C      | `QUESTION`   | The full question text                               | `What is the plural of "horse" in French?`   |
| D      | `A`          | Option A                                             | `Chevals`                                    |
| E      | `B`          | Option B                                             | `Chevaux`                                    |
| F      | `C`          | Option C                                             | `Chevales`                                   |
| G      | `D`          | Option D                                             | `Chevaus`                                    |
| H      | `ANSWER`     | The correct answer text                              | `Chevaux`                                    |
| I      | `LETTER`     | The correct option letter (A / B / C / D)            | `B`                                          |

**Example `QUESTIONS` tab:**

| BATCH | # | QUESTION                                | A          | B          | C          | D          | ANSWER     | LETTER |
|-------|---|-----------------------------------------|------------|------------|------------|------------|------------|--------|
| 1     | 1 | What is the past tense of "go"?         | goed       | went       | gone       | going      | went       | B      |
| 1     | 2 | How do you say "since" in English?      | since      | during     | from       | for        | since      | A      |
| 1     | 3 | What completes: "I look forward ___"?   | for        | since      | during     | to         | to         | D      |
| …     |   |                                         |            |            |            |            |            |        |
| 1     | 40| What does "yet" mean?                   | already    | still      | ever       | already    | already    | B      |
| 2     | 1 | Quel est le pluriel de « cheval » ?     | Chevals    | Chevaux    | Chevales   | Chevaus    | Chevaux    | B      |
| 2     | 2 | Que signifie « pourtant » ?             | donc       | aussi      | car        | pourtant   | pourtant   | A      |
| …     |   |                                         |            |            |            |            |            |        |

---

## 🔄 Daily Workflow for the Client

```
Day 1  →  Fill BATCH 1 in CONFIG + 40 rows in QUESTIONS (BATCH=1)  →  Run system  →  Video 1
Day 2  →  Add BATCH 2 in CONFIG + 40 new rows in QUESTIONS (BATCH=2)  →  Run system  →  Video 2
Day 3  →  Add BATCH 3 in CONFIG + 40 new rows …  →  Run system  →  Video 3
```

### Rules

1. **Never edit or delete old rows** — just keep adding new batches below.
2. **BATCH number must match** between the `CONFIG` tab and the `QUESTIONS` tab.
3. **Question `#` restarts at 1** for each new batch.
4. **STATUS column in CONFIG** — leave it blank. The system writes `DONE` + timestamp after processing.
5. **VIDEO_URL column in CONFIG** — leave it blank. The system writes the Google Drive link after upload.
6. The system **only processes batches where STATUS is empty** — so old batches are skipped automatically.

---

## 🌍 Supported Language Codes

| Code | Language     | Recommended Voice |
|------|-------------|-------------------|
| `en` | English     | Puck, Zephyr      |
| `fr` | French      | Kore, Fenrir      |
| `es` | Spanish     | Aoede, Leda       |
| `de` | German      | Charon, Orus      |
| `ar` | Arabic      | Sadachbia, Alnilam|
| `pt` | Portuguese  | Achernar, Schedar |
| `hi` | Hindi       | Algieba, Despina  |
| `ja` | Japanese    | Callirrhoe, Umbriel|
| `ko` | Korean      | Autonoe, Iapetus  |
| `tr` | Turkish     | Gacrux, Sulafat   |

> Full list of 30 Gemini voices: Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat.
>
> Any voice works with any language — Gemini auto-detects the text language.

---

## ⚠️ Common Mistakes to Avoid

| ❌ Don't                                    | ✅ Do                                         |
|---------------------------------------------|-----------------------------------------------|
| Skip the BATCH column                       | Always fill BATCH in both tabs                |
| Put 80 questions in one batch               | Keep ~40 questions per batch (≈ 8.5 min video)|
| Use batch 1 again for new questions         | Use the next batch number (2, 3, 4…)         |
| Write the answer letter as lowercase `b`    | Use uppercase: `A`, `B`, `C`, or `D`         |
| Leave QUESTION or any option cell empty     | Fill every cell — no blanks allowed           |
| Edit the STATUS or VIDEO_URL columns        | Those are auto-filled by the system           |
| Change column order or rename headers       | Keep headers exactly as shown above           |
