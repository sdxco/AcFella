"""
Acoustic Fella - Flask Web Application

Main application entry point for the web interface.
Includes project management, porous absorber calculator, and all analysis tools.
"""

import os
import json
import tempfile
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Import acoustic modules
from acoustic_fella.core.room_modes import RoomModeCalculator
from acoustic_fella.core.absorption import AbsorptionCalculator
from acoustic_fella.core.reverberation import ReverberationAnalyzer, RoomTargets
from acoustic_fella.core.schroeder import SchroederAnalyzer
from acoustic_fella.core.porous_absorber import PorousAbsorberCalculator
from acoustic_fella.core.projects import ProjectManager
from acoustic_fella.parsers.rew_parser import REWParser, REWAnalyzer
from acoustic_fella.treatment.recommendation_engine import (
    TreatmentRecommendationEngine,
    generate_quick_recommendations
)
from acoustic_fella.treatment.speaker_placement import (
    SpeakerPlacementOptimizer,
    quick_speaker_placement
)
from acoustic_fella.treatment.panel_calculator import PanelConstructionCalculator
from acoustic_fella.treatment.mls_generator import (
    MLSGenerator,
    design_hybrid_panel,
    get_all_mls_orders
)

# Initialize Flask app
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

ALLOWED_EXTENSIONS = {'txt', 'frd', 'wav', 'mdat', 'png', 'jpg', 'jpeg'}

# Initialize project manager
project_manager = ProjectManager()
porous_calc = PorousAbsorberCalculator()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_project_context():
    """Get project from query param if present."""
    pid = request.args.get('project')
    if pid:
        return project_manager.get(pid)
    return None


def all_projects_list():
    """Return list of project dicts for template context."""
    return [p.to_dict() for p in project_manager.list_all()]


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
def index():
    projects = all_projects_list()
    return render_template('index.html', projects=projects)


@app.route('/projects')
def projects():
    return render_template('projects.html', projects=all_projects_list())


@app.route('/project/<project_id>')
def project_detail(project_id):
    p = project_manager.get(project_id)
    if not p:
        return render_template('projects.html', projects=all_projects_list()), 404
    return render_template('project_detail.html', project=p.to_dict())


@app.route('/room-analysis')
def room_analysis():
    project = get_project_context()
    pdict = project.to_dict() if project else None
    return render_template('room_analysis.html', project=pdict, projects=all_projects_list())


@app.route('/treatment-plan')
def treatment_plan():
    project = get_project_context()
    pdict = project.to_dict() if project else None
    return render_template('treatment_plan.html', project=pdict, projects=all_projects_list())


@app.route('/diy-calculator')
def diy_calculator():
    return render_template('diy_calculator.html')


@app.route('/hybrid-panel')
def hybrid_panel():
    return render_template('hybrid_panel.html')


@app.route('/hybrid-panel-simple')
def hybrid_panel_simple():
    return render_template('hybrid_panel_simple.html')


@app.route('/speaker-placement')
def speaker_placement():
    project = get_project_context()
    pdict = project.to_dict() if project else None
    return render_template('speaker_placement.html', project=pdict, projects=all_projects_list())


@app.route('/magic')
def magic_analysis():
    project = get_project_context()
    pdict = project.to_dict() if project else None
    return render_template('magic_analysis.html', project=pdict, projects=all_projects_list())


@app.route('/porous-absorber')
def porous_absorber():
    presets = porous_calc.get_material_presets()
    return render_template('porous_absorber.html', presets=presets)


# ============================================================================
# PROJECT API
# ============================================================================

@app.route('/api/projects', methods=['GET'])
def api_list_projects():
    return jsonify({"success": True, "projects": all_projects_list()})


@app.route('/api/projects', methods=['POST'])
def api_create_project():
    data = request.get_json()
    try:
        p = project_manager.create(
            name=data['name'],
            description=data.get('description', ''),
            room_type=data.get('room_type', 'mixing_mastering'),
            geometry=data.get('geometry'),
            tags=data.get('tags', []),
            notes=data.get('notes', '')
        )
        return jsonify({"success": True, "project": p.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/projects/<project_id>', methods=['GET'])
def api_get_project(project_id):
    p = project_manager.get(project_id)
    if not p:
        return jsonify({"success": False, "error": "Not found"}), 404
    return jsonify({"success": True, "project": p.to_dict()})


@app.route('/api/projects/<project_id>', methods=['PUT'])
def api_update_project(project_id):
    data = request.get_json()
    try:
        p = project_manager.update(project_id, data)
        if not p:
            return jsonify({"success": False, "error": "Not found"}), 404
        return jsonify({"success": True, "project": p.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def api_delete_project(project_id):
    ok = project_manager.delete(project_id)
    if not ok:
        return jsonify({"success": False, "error": "Not found"}), 404
    return jsonify({"success": True})


# ============================================================================
# POROUS ABSORBER API
# ============================================================================

@app.route('/api/porous-absorber', methods=['POST'])
def api_porous_absorber():
    data = request.get_json()
    try:
        result = porous_calc.calculate(
            thickness_mm=float(data.get('thickness_mm', 100)),
            flow_resistivity=float(data.get('flow_resistivity', 10000)),
            air_gap_mm=float(data.get('air_gap_mm', 0)),
            model=data.get('model', 'miki'),
        )
        incidence = data.get('incidence', 'both')
        resp = {
            "success": True,
            "frequencies": result.frequencies.tolist(),
            "nrc": round(result.nrc, 2),
            "saa": round(result.saa, 2),
            "effective_low_freq": round(result.effective_low_freq, 1),
            "total_depth_mm": result.total_depth_mm,
            "model": result.model,
        }
        if incidence in ('normal', 'both'):
            resp['absorption_normal'] = [round(float(x), 4) for x in result.absorption_normal]
        if incidence in ('random', 'both'):
            resp['absorption_random'] = [round(float(x), 4) for x in result.absorption_random]
        return jsonify(resp)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/porous-absorber/presets', methods=['GET'])
def api_porous_presets():
    return jsonify({"success": True, "presets": porous_calc.get_material_presets()})


# ============================================================================
# ROOM ANALYSIS API (enhanced - amroc-style)
# ============================================================================

@app.route('/api/analyze-room', methods=['POST'])
def analyze_room():
    data = request.get_json()
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        room_type = data.get('room_type', 'mixing_mastering')
        rt60 = float(data.get('rt60', 0.3))
        max_frequency = float(data.get('max_frequency', 500))

        # Convert to metric if needed
        if not use_metric:
            length *= 0.3048
            width *= 0.3048
            height *= 0.3048

        mode_calc = RoomModeCalculator(length, width, height, True)
        modes = mode_calc.calculate_all_modes(max_frequency=max_frequency)

        # Schroeder
        volume = length * width * height
        schroeder_analyzer = SchroederAnalyzer(volume, rt60, True)
        schroeder = schroeder_analyzer.analyze()
        treatment_zones = schroeder_analyzer.get_treatment_zones()

        # Ratios
        ratios_data = mode_calc.get_optimal_ratios()

        # Bonello
        bonello = mode_calc.bonello_analysis()

        # Room info
        surface_area = 2 * (length*width + length*height + width*height)

        # Problems - find clustered modes
        problems = []
        freqs = sorted([m.frequency for m in modes])
        for i in range(len(freqs) - 1):
            gap = freqs[i+1] - freqs[i]
            if gap < 5 and freqs[i] < 300:
                problems.append({
                    "frequency": freqs[i],
                    "severity": "high" if gap < 2 else "medium",
                    "recommendation": f"Modes at {freqs[i]:.1f} Hz and {freqs[i+1]:.1f} Hz are very close ({gap:.1f} Hz apart). Bass trapping recommended."
                })

        return jsonify({
            "success": True,
            "room_info": {
                "volume": round(volume, 2),
                "surface_area": round(surface_area, 2),
                "length": round(length, 3),
                "width": round(width, 3),
                "height": round(height, 3),
            },
            "modes": [
                {
                    "frequency": round(m.frequency, 1),
                    "type": m.mode_type.name.lower(),
                    "indices": m.mode_string,
                    "wavelength": round(343.0 / m.frequency, 2) if m.frequency > 0 else 0,
                }
                for m in modes
            ],
            "schroeder": {
                "frequency": round(schroeder.schroeder_frequency, 1),
                "transition_low": round(schroeder.schroeder_frequency * 0.5, 1),
                "transition_high": round(schroeder.schroeder_frequency * 2.0, 1),
                "bass_trap_range": schroeder.bass_trap_range,
                "absorber_range": schroeder.absorber_range,
            },
            "ratios": ratios_data,
            "bonello": bonello,
            "problems": problems,
            "treatment_zones": treatment_zones,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ============================================================================
# EXISTING API ENDPOINTS (preserved from original)
# ============================================================================

@app.route('/api/upload-rew', methods=['POST'])
def upload_rew():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        ext = filename.rsplit('.', 1)[1].lower()
        if ext in ['png', 'jpg', 'jpeg']:
            os.remove(filepath)
            return jsonify({
                "success": True,
                "message": "Image uploaded. For detailed analysis, export REW data as .txt or .mdat.",
                "data_type": "image"
            })
        parser = REWParser()
        measurement = parser.parse(filepath)
        analyzer = REWAnalyzer(measurement)
        analysis = analyzer.analyze()
        os.remove(filepath)
        return jsonify({
            "success": True,
            "data_type": "measurement",
            "frequencies": measurement.frequency_response.frequencies[:2000].tolist(),
            "magnitude": measurement.frequency_response.magnitude[:2000].tolist(),
            "peaks": analysis['peaks'][:20],
            "dips": analysis['dips'][:20],
            "problem_frequencies": analysis['problem_frequencies'][:20],
            "summary": analysis['summary']
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/generate-treatment-plan', methods=['POST'])
def generate_treatment_plan():
    data = request.get_json()
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        room_type = data.get('room_type', 'mixing_mastering')
        engine = TreatmentRecommendationEngine(length, width, height, use_metric, room_type)
        plan = engine.generate_treatment_plan()
        return jsonify({
            "success": True,
            "treatment_plan": {
                "items": [
                    {
                        **item.to_dict(),
                        "priority_label": 'Critical' if item.priority == 1 else 'High' if item.priority == 2 else 'Medium' if item.priority == 3 else 'Low',
                        "name": item.treatment_type.value.replace('_', ' ').title(),
                    }
                    for item in plan.get_by_priority()
                ],
                "bill_of_materials": {
                    k: v for k, v in plan.get_bill_of_materials().items()
                },
                "notes": plan.notes
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/speaker-placement', methods=['POST'])
def calculate_speaker_placement():
    data = request.get_json()
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        speaker_type = data.get('speaker_type', 'nearfield')
        optimizer = SpeakerPlacementOptimizer(length, width, height, use_metric)
        report = optimizer.generate_placement_report(speaker_type)
        return jsonify({"success": True, "placement": report})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/design-panel', methods=['POST'])
def design_panel():
    data = request.get_json()
    try:
        use_metric = data.get('unit', 'metric') == 'metric'
        calculator = PanelConstructionCalculator(use_metric)
        panel_type = data.get('panel_type', 'broadband_absorber')
        width = float(data.get('width', 600 if use_metric else 24))
        height = float(data.get('height', 1200 if use_metric else 48))
        target_freq = float(data.get('target_frequency', 250))

        if panel_type == 'broadband_absorber':
            result = calculator.design_broadband_absorber(width=width, height=height, target_low_freq=target_freq)
        elif panel_type == 'corner_bass_trap':
            result = calculator.design_corner_bass_trap(height=height, target_low_freq=target_freq)
        elif panel_type == 'helmholtz_resonator':
            result = calculator.design_helmholtz_resonator(target_frequency=target_freq, width=width, height=height)
        elif panel_type == 'qrd_diffuser':
            prime = int(data.get('prime_number', 7))
            design_freq = target_freq
            result = calculator.design_qrd_diffuser(prime=prime, design_freq=design_freq, width=width, height=height)
        elif panel_type == 'membrane_absorber':
            result = calculator.design_membrane_absorber(target_frequency=target_freq, width=width, height=height)
        else:
            return jsonify({"success": False, "error": f"Unknown panel type: {panel_type}"}), 400

        panel_dict = result.to_dict()
        panel_dict['type'] = panel_type
        return jsonify({
            "success": True,
            "panel": panel_dict
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/design-hybrid-panel', methods=['POST'])
def api_design_hybrid_panel():
    data = request.get_json()
    try:
        width = int(data.get('width', 600))
        height = int(data.get('height', 600))
        well_width_mm = int(data.get('well_width_mm', 50))
        absorber_depth_mm = int(data.get('absorber_depth_mm', 50))
        layout = data.get('layout', 'mls')
        generate_inverse = data.get('generate_inverse', True)
        result = design_hybrid_panel(
            width_mm=width,
            height_mm=height,
            well_width_mm=well_width_mm,
            absorber_depth_mm=absorber_depth_mm,
            layout=layout,
            seed=1,
            generate_inverse=generate_inverse
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/mls-orders', methods=['GET'])
def api_mls_orders():
    try:
        orders = get_all_mls_orders()
        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/quick-analysis', methods=['POST'])
def quick_analysis():
    data = request.get_json()
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        room_type = data.get('room_type', 'mixing_mastering')
        recommendations = generate_quick_recommendations(length, width, height, room_type, use_metric)
        speaker = quick_speaker_placement(length, width, height, use_metric)
        return jsonify({"success": True, "analysis": recommendations, "speaker_placement": speaker})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/magic-analysis', methods=['POST'])
def magic_analysis_api():
    try:
        length = float(request.form['length'])
        width = float(request.form['width'])
        height = float(request.form['height'])
        use_metric = request.form.get('unit', 'metric') == 'metric'
        room_type = request.form.get('room_type', 'mixing_mastering')
        speaker_type = request.form.get('speaker_type', 'nearfield')
        unit_label = 'metric' if use_metric else 'imperial'

        mode_calc = RoomModeCalculator(length, width, height, use_metric)
        modes_data = mode_calc.calculate_all_modes(max_frequency=300)
        bonello = mode_calc.bonello_analysis()

        volume = length * width * height
        estimated_t60 = 0.5
        schroeder_calc = SchroederAnalyzer(volume, estimated_t60, use_metric)
        schroeder = schroeder_calc.analyze()

        ratios_data = mode_calc.get_optimal_ratios()
        ratios = ratios_data['current_ratios']
        ratio_quality = ratios_data['comparisons'][ratios_data['best_match']]['match_quality']

        target_t60_map = {
            'mixing_mastering': '200-250',
            'recording': '250-300',
            'music_production': '200-300',
            'home_theater': '300-400'
        }
        target_t60 = target_t60_map.get(room_type, '200-300')

        # REW file
        rew_data = None
        rew_file = request.files.get('rew_file')
        if rew_file and rew_file.filename:
            filename = secure_filename(rew_file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if ext in ['png', 'jpg', 'jpeg']:
                rew_data = {
                    'is_image': True,
                    'message': 'Image upload detected. Export REW data as .txt or .mdat for best results.',
                    'frequencies': [], 'magnitude': [], 'peaks': [], 'dips': [], 'problem_frequencies': []
                }
            elif ext in ALLOWED_EXTENSIONS:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                rew_file.save(filepath)
                try:
                    parser = REWParser()
                    measurement = parser.parse(filepath)
                    analyzer = REWAnalyzer(measurement)
                    analysis = analyzer.analyze()
                    rew_data = {
                        'is_image': False,
                        'frequencies': measurement.frequency_response.frequencies[:1000].tolist(),
                        'magnitude': measurement.frequency_response.magnitude[:1000].tolist(),
                        'peaks': [{'freq': p['frequency'], 'mag': p['magnitude']} for p in analysis['peaks'][:10]],
                        'dips': [{'freq': d['frequency'], 'mag': d['magnitude']} for d in analysis['dips'][:10]],
                        'problem_frequencies': analysis['problem_frequencies'][:10]
                    }
                    os.remove(filepath)
                except Exception as e:
                    rew_data = {'error': f'Could not parse REW file: {str(e)}', 'frequencies': [], 'magnitude': [], 'peaks': [], 'dips': [], 'problem_frequencies': []}

        # Treatment plan
        engine = TreatmentRecommendationEngine(length, width, height, use_metric, room_type)
        problem_freqs = []
        if rew_data and 'problem_frequencies' in rew_data:
            problem_freqs = rew_data['problem_frequencies']
        plan = engine.generate_treatment_plan(measured_modes=problem_freqs)

        # Speaker
        optimizer = SpeakerPlacementOptimizer(length, width, height, use_metric)
        speaker_report = optimizer.generate_placement_report(speaker_type)

        # DIY panels
        calculator = PanelConstructionCalculator(use_metric)
        diy_panels = []
        try:
            bt = calculator.design_corner_bass_trap(height=height, target_low_freq=60)
            d = bt.to_dict(); d['type'] = 'corner_bass_trap'
            diy_panels.append(d)
        except: pass
        try:
            ab = calculator.design_broadband_absorber(width=600 if use_metric else 24, height=1200 if use_metric else 48, target_low_freq=250)
            d = ab.to_dict(); d['type'] = 'broadband_absorber'
            diy_panels.append(d)
        except: pass
        try:
            df = calculator.design_qrd_diffuser(prime=7, design_freq=500, width=600 if use_metric else 24, height=600 if use_metric else 24)
            d = df.to_dict(); d['type'] = 'qrd_diffuser'
            diy_panels.append(d)
        except: pass

        response = {
            'success': True,
            'unit': unit_label,
            'room': {
                'length': length, 'width': width, 'height': height, 'unit': unit_label,
                'volume': round(volume, 2), 'schroeder_frequency': round(schroeder.schroeder_frequency, 1),
                'target_t60': target_t60, 'ratios': ratios, 'ratio_quality': ratio_quality
            },
            'modes': {
                'modes': [
                    {'frequency': round(m.frequency, 1), 'type': m.mode_type.name.capitalize(), 'indices': m.mode_string}
                    for m in modes_data[:50]
                ],
                'bonello_pass': bonello['passes_bonello'],
                'bonello_notes': bonello['recommendation']
            },
            'rew': rew_data,
            'speaker_placement': speaker_report,
            'treatment_plan': {
                'items': [
                    {
                        **item.to_dict(),
                        'priority_label': 'Critical' if item.priority == 1 else 'High' if item.priority == 2 else 'Medium' if item.priority == 3 else 'Low',
                        'name': item.treatment_type.value.replace('_', ' ').title(),
                        'description': f"Treat {item.location.value.replace('_', ' ')} to control {', '.join([f'{f:.0f}Hz' for f in item.target_frequencies[:3]])}",
                        'placement': item.location.value.replace('_', ' ').title(),
                        'dimensions': f"{item.dimensions.get('width', 0):.0f} x {item.dimensions.get('height', 0):.0f} x {item.dimensions.get('depth', 0):.0f} {'mm' if use_metric else 'in'}",
                        'quantity': 1
                    }
                    for item in plan.get_by_priority()
                ],
                'bill_of_materials': [
                    {'item': v['material'], 'quantity': v['count'], 'unit': 'panels', 'notes': f"Total area: {v['total_area']:.2f} sq {'m' if use_metric else 'ft'}"}
                    for k, v in plan.get_bill_of_materials().items()
                ],
                'notes': plan.notes
            },
            'diy_panels': diy_panels
        }
        return jsonify(response)
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 400


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
