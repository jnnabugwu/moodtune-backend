# Mood engines compared: rule-based vs CLAP vs YAMNet

200 Jamendo tracks: upbeat 50, serene 50, charged 50, reflective 50. Truth = the bucket implied by the track's Jamendo mood tags (noisy). Chance = 25%.

Accuracy shows a 95% confidence interval; balanced = mean per-bucket recall.

| Method | Accuracy (95% CI) | Balanced | Model | CPU time |
|---|---|---|---|---|
| Rule-based (backend) | 32% (26%-39%) | 32% | - | 7410 ms / whole track |
| CLAP general (prompt ensemble) | 37% (31%-44%) | 37% | 28M params | 19 ms / 10 s window |
| CLAP general (single prompt) | 43% (36%-50%) | 43% | | |
| CLAP general (ensemble + calibrated) | 50% (44%-57%) | 50% | | |
| CLAP music (prompt ensemble) | 23% (18%-29%) | 23% | 69M params | 33 ms / 10 s window |
| CLAP music (single prompt) | 27% (21%-34%) | 27% | | |
| CLAP music (ensemble + calibrated) | 28% (23%-35%) | 29% | | |
| YAMNet (raw) | 44% (37%-50%) | 44% | 4 MB tflite (3.7M params) | 0.5 ms / 0.975 s frame |
| YAMNet (calibrated) | 44% (38%-51%) | 44% | | |
| **CLAP general + YAMNet blend** | 48% (41%-55%) | 48% | 34 + 4 MB | |

## Confusion matrices

### Rule-based (backend)

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 34 | 9 | 1 | 6 |
| **serene** | 9 | 6 | 1 | 34 |
| **charged** | 30 | 13 | 3 | 4 |
| **reflective** | 19 | 9 | 1 | 21 |

Backend label distribution: {'energetic': 88, 'calm': 37, 'sad': 65, 'happy': 4, 'angry': 6}

### CLAP general

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 28 | 0 | 21 | 1 |
| **serene** | 35 | 2 | 4 | 9 |
| **charged** | 15 | 0 | 35 | 0 |
| **reflective** | 21 | 2 | 18 | 9 |

CLAP general label distribution: {'energetic': 69, 'happy': 30, 'angry': 78, 'sad': 19, 'calm': 4}

### CLAP general, calibrated

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 28 | 3 | 16 | 3 |
| **serene** | 10 | 34 | 0 | 6 |
| **charged** | 17 | 2 | 30 | 1 |
| **reflective** | 12 | 20 | 9 | 9 |

### CLAP music

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 25 | 0 | 25 | 0 |
| **serene** | 31 | 0 | 19 | 0 |
| **charged** | 28 | 1 | 21 | 0 |
| **reflective** | 30 | 0 | 20 | 0 |

CLAP music label distribution: {'happy': 114, 'angry': 85, 'calm': 1}

### CLAP music, calibrated

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 28 | 4 | 12 | 6 |
| **serene** | 19 | 7 | 14 | 10 |
| **charged** | 27 | 4 | 12 | 7 |
| **reflective** | 23 | 6 | 11 | 10 |

### YAMNet (raw)

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 47 | 3 | 0 | 0 |
| **serene** | 24 | 23 | 1 | 2 |
| **charged** | 34 | 1 | 15 | 0 |
| **reflective** | 23 | 25 | 0 | 2 |

YAMNet label distribution: {'happy': 46, 'energetic': 82, 'calm': 52, 'sad': 4, 'angry': 16}

### YAMNet (calibrated)

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 20 | 2 | 9 | 19 |
| **serene** | 7 | 4 | 9 | 30 |
| **charged** | 9 | 2 | 31 | 8 |
| **reflective** | 3 | 5 | 8 | 34 |

## YAMNet sound tags (sample)

| Track | Truth | Top tags |
|---|---|---|
| What Is Love | upbeat | Pop music, Singing, Lullaby, Christian music, Christmas music |
| Strong | upbeat | Rhythm and blues, Soul music, Singing, Christian music, Funk |
| Do You Still Dream | upbeat | Pop music, Music for children, Happy music, Singing, Exciting music |
| Liquid Blue | upbeat | Disco, House music, Dance music, Electronic music, Funk |
| What Do You Know | upbeat | Pop music, Jingle (music), Music for children, Independent music, Singing |
| Reach the Stars | upbeat | Rhythm and blues, Plucked string instrument, Music of Africa, Happy music, Music for children |
| Here to Stay (feat. Amanda Dro | upbeat | Dubstep, Electronic music, Dance music, Pop music, Exciting music |
| These Nights | upbeat | Independent music, Grunge, Rock music, Progressive rock, Psychedelic rock |
| New Life | upbeat | Independent music, Pop music, Singing, Christian music, Christmas music |
| Way to Success | upbeat | Background music, Video game music, Electronic music, Soundtrack music, Electronica |
| Horizons | serene | Acoustic guitar, Plucked string instrument, Guitar, Singing, Christian music |
| Chances | serene | Dubstep, Electronic music, Singing, Rhythm and blues, Pop music |
| Lofi Chillout Hip Hop Beat | serene | Rhythm and blues, Soul music, Organ, Steelpan, Electronic music |
| Dj Rostej - Long Way | serene | Electronic music, Electronica, Rhythm and blues, Drum and bass, Synthesizer |
| Into The Dream | serene | Christian music, Christmas music, Happy music, Country, Singing |
| Prelude in C# minor | serene | Piano, Keyboard (musical), Electric piano, Tender music, Classical music |
| Adult Only & SaReGaMa - Afterz | serene | Electronic music, Dubstep, Electronica, Rhythm and blues, Electronic dance music |
| Stories from Emona III | serene | Piano, Electric piano, Keyboard (musical), Lullaby, Tender music |
| La sixième porte de Shanaaghar | serene | Background music, Theme music, Tender music, New-age music, Independent music |
| Our Universe | serene | Electronic music, Dubstep, Synthesizer, Sampler, Electronica |
| Los money - Pueto pa lo mio re | charged | Hip hop music, Rapping, Singing, Exciting music, Pop music |
| Talk About Your Feelings | charged | Music of Africa, Rhythm and blues, Reggae, Plucked string instrument, Afrobeat |
| Backstabber | charged | Rhythm and blues, Pop music, Hip hop music, Exciting music, Singing |
| Iron dinosaurs | charged | Heavy metal, Rock music, Progressive rock, Angry music, Electronic music |
| The Metalcore | charged | Heavy metal, Rock music, Angry music, Exciting music, Progressive rock |
| Howling Wolf | charged | Rock music, Psychedelic rock, Independent music, Plucked string instrument, Guitar |
| La Machine | charged | Electronic music, Drum machine, Sampler, Synthesizer, Reggae |
| more birds more bees | charged | Christmas music, Music for children, Singing, Jingle (music), Happy music |
| PRESSURE | charged | Hip hop music, Rapping, Singing, Rhythm and blues, Exciting music |
| Soda Stereo | charged | Rock music, Heavy metal, Rattle (instrument), Electronic music, Funk |
| Take it | reflective | Rhythm and blues, Electronic music, Dubstep, Lullaby, Singing |
| Give Me a Change | reflective | Rhythm and blues, Soul music, Pop music, Christian music, Singing |
| A Better Place | reflective | Plucked string instrument, Guitar, Strum, Acoustic guitar, Singing |
| Mi razón de ser / de La Banda  | reflective | Singing, Jingle (music), Christmas music, Country, Christian music |
| I Do | reflective | Piano, Keyboard (musical), Electric piano, Tender music, Lullaby |
| afternoon nap | reflective | Electronic music, Video game music, Background music, Dubstep, Sound effect |
| Horse Tamer | reflective | Plucked string instrument, Country, Guitar, Acoustic guitar, Singing |
| sensate | reflective | Electronic music, Dubstep, Electronica, Synthesizer, Keyboard (musical) |
| Stefan The Poker Player | reflective | Electronic music, Disco, House music, Techno, Electronica |
| No Doctor | reflective | Lullaby, Tender music, Singing, Sad music, Christmas music |

### CLAP general + YAMNet blend

| truth \ predicted | upbeat | serene | charged | reflective |
|---|---|---|---|---|
| **upbeat** | 30 | 1 | 9 | 10 |
| **serene** | 11 | 11 | 5 | 23 |
| **charged** | 15 | 2 | 30 | 3 |
| **reflective** | 14 | 4 | 7 | 25 |
