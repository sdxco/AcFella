# 🎛️ Acoustic Fella

**Professional Room Acoustics Treatment Software**

Acoustic Fella is a comprehensive tool for analyzing room acoustics and generating treatment plans to achieve professional-grade sound in any space. Whether you're building a home studio, mixing room, or recording space, this software helps you achieve a flat frequency response and optimal reverberation time.

## ✨ Features

### Room Analysis
- **Room Mode Calculator**: Uses the Rayleigh equation to identify axial, tangential, and oblique room modes
- **Schroeder Frequency Analysis**: Determines the transition point between modal and diffuse behavior
- **Bonello Criterion**: Evaluates modal distribution quality using octave band analysis
- **REW File Import**: Parse Room EQ Wizard measurements (.txt, .frd, .mdat formats)

### Treatment Planning
- **Automated Recommendations**: Get prioritized treatment suggestions based on room analysis
- **Bass Trap Placement**: Tri-corner and wall-corner optimization
- **First Reflection Points**: Calculate exact positions for absorption panels
- **Diffuser Placement**: Rear wall and ceiling treatment recommendations
- **Bill of Materials**: Complete shopping list with quantities and dimensions

### DIY Panel Calculator
- **Broadband Absorbers**: Design absorption panels with various insulation types
- **Corner Bass Traps**: Tri-corner traps sized for your room's modal problems
- **Helmholtz Resonators**: Tuned absorbers for specific problem frequencies
- **QRD Diffusers**: Quadratic residue diffuser designs with well depth calculations
- **Membrane Absorbers**: Panel resonator designs for low-mid frequency control

### Speaker Placement
- **Optimal Positioning**: Using the 38% rule and equilateral triangle formation
- **SBIR Analysis**: Speaker-boundary interference response calculations
- **Subwoofer Placement**: Multiple options with pressure zone optimization
- **Visual Room Layout**: Interactive room diagram with positions

## 🎯 Target Performance

- **Frequency Response**: ±3dB from 20Hz to 20kHz
- **RT60**: 200-300ms (optimized for your room type)
  - Mixing/Mastering: 200-250ms
  - Recording: 250-300ms
  - Music Production: 200-300ms

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Local Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd ACFELLA

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

Visit `http://localhost:5000` in your browser.

### Deploy to Railway (Online Access)

1. **Create Railway Account**
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub

2. **Deploy from GitHub**
   - Push your code to GitHub
   - In Railway, click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Railway will automatically:**
   - Detect Python project
   - Install dependencies from `requirements.txt`
   - Run using the `Procfile` configuration
   - Assign a public URL (e.g., `your-app.railway.app`)

4. **Access Your App**
   - Railway will provide a public URL
   - Your app will be accessible from anywhere!

**Alternative: Deploy from CLI**

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Deploy
railway up
```

Your app will be live at the URL Railway provides!

## 🛠️ Development

### Installation

1. Clone or download this repository
2. Navigate to the project directory
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
python run.py
```

5. Open your browser to `http://localhost:5000`

### Quick Start

1. **Room Analysis**: Enter your room dimensions and target use case
2. **Upload REW Data** (optional): Import measurements for detailed analysis
3. **Review Modal Problems**: See which frequencies need treatment
4. **Generate Treatment Plan**: Get a prioritized list of acoustic treatments
5. **DIY Calculator**: Design and build your own treatment panels
6. **Speaker Placement**: Optimize monitor and subwoofer positions

## 📐 Acoustic Formulas Used

### Rayleigh Equation (Room Modes)
```
f = (c/2) × √[(p/L)² + (q/W)² + (r/H)²]
```
Where c = speed of sound, L/W/H = room dimensions, p/q/r = mode indices

### Schroeder Frequency
```
fc = 2000 × √(T60/V)
```
Where T60 = reverberation time, V = room volume

### Sabine Equation (RT60)
```
T60 = 0.161V / A
```
Where V = volume, A = total absorption (Sabins)

### Eyring Equation (RT60 for dead rooms)
```
T60 = 0.161V / [-S × ln(1-α)]
```
Where S = total surface area, α = average absorption coefficient

### Helmholtz Resonator
```
f = (c/2π) × √[S/(V × L')]
```
Where S = neck area, V = cavity volume, L' = effective neck length

## 📁 Project Structure

```
acoustic_fella/
├── core/                    # Core calculation modules
│   ├── room_modes.py        # Room mode calculator
│   ├── schroeder.py         # Schroeder frequency analysis
│   ├── absorption.py        # Sabine/Eyring calculations
│   └── reverberation.py     # RT60 analysis
├── parsers/
│   └── rew_parser.py        # REW file parser
├── treatment/
│   ├── recommendation_engine.py  # Treatment planner
│   ├── speaker_placement.py      # Speaker/listener positioning
│   └── panel_calculator.py       # DIY panel designs
└── web/
    ├── app.py               # Flask application
    ├── templates/           # HTML templates
    └── static/              # CSS/JS assets
```

## 🔬 Technical Details

### Room Mode Types
- **Axial**: Parallel surfaces (strongest, 1 dimension)
- **Tangential**: Two pairs of surfaces (moderate, 2 dimensions)
- **Oblique**: All three pairs (weakest, 3 dimensions)

### Treatment Priority
1. Low-frequency modal control (bass traps)
2. First reflection management
3. Rear wall treatment (absorption/diffusion)
4. RT60 optimization
5. Flutter echo prevention

### Material Database
The system includes absorption coefficients for common materials:
- Rockwool / Stone Wool (various densities)
- Fiberglass (OC 703, OC 705)
- Polyester fiber panels
- Acoustic foam
- Diffuser materials

## 📊 Room Targets by Use Case

| Room Type | RT60 Target | Focus |
|-----------|-------------|-------|
| Mixing/Mastering | 200-250ms | Flat response, controlled reflections |
| Recording (Vocals) | 250-300ms | Natural sound, minimal coloration |
| Music Production | 200-300ms | Balanced for both tracking and mixing |

## 🛠️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze-room` | POST | Full room analysis |
| `/api/upload-rew` | POST | Upload and parse REW file |
| `/api/generate-treatment-plan` | POST | Create treatment recommendations |
| `/api/speaker-placement` | POST | Calculate optimal positions |
| `/api/design-panel` | POST | DIY panel specifications |
| `/api/quick-analysis` | POST | Fast room mode check |

## 📖 References

This software implements concepts from:
- "Master Handbook of Acoustics" by F. Alton Everest
- "Springer Handbook of Acoustics" 
- AES (Audio Engineering Society) standards
- ITU-R BS.1116 recommendations

## ⚠️ Disclaimer

This software provides recommendations based on acoustic principles and calculations. Results may vary based on construction materials, room irregularities, and other factors. Professional acoustic consultation is recommended for critical listening spaces.

## 📄 License

MIT License - Feel free to use and modify for your projects.

---

**Built with ❤️ for audio professionals and enthusiasts**
