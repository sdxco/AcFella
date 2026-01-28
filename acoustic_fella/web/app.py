"""
Acoustic Fella - Flask Web Application

Main application entry point for the web interface.
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


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')


@app.route('/room-analysis')
def room_analysis():
    """Room analysis page"""
    return render_template('room_analysis.html')


@app.route('/treatment-plan')
def treatment_plan():
    """Treatment plan page"""
    return render_template('treatment_plan.html')


@app.route('/diy-calculator')
def diy_calculator():
    """DIY panel calculator page"""
    return render_template('diy_calculator.html')


@app.route('/hybrid-panel')
def hybrid_panel():
    """Hybrid MLS panel designer page"""
    return render_template('hybrid_panel.html')


@app.route('/hybrid-panel-simple')
def hybrid_panel_simple():
    """Simplified hybrid panel designer for beginners."""
    return render_template('hybrid_panel_simple.html')


@app.route('/speaker-placement')
def speaker_placement():
    """Speaker placement page"""
    return render_template('speaker_placement.html')


@app.route('/magic')
def magic_analysis():
    """Complete magic analysis page"""
    return render_template('magic_analysis.html')


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/analyze-room', methods=['POST'])
def analyze_room():
    """
    Analyze room dimensions and calculate modes.
    
    Expected JSON:
    {
        "length": float,
        "width": float,
        "height": float,
        "unit": "metric" | "imperial",
        "room_type": string
    }
    """
    data = request.get_json()
    
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        room_type = data.get('room_type', 'mixing_mastering')
        
        # Calculate room modes
        mode_calc = RoomModeCalculator(length, width, height, use_metric)
        report = mode_calc.generate_report()
        
        # Calculate Schroeder frequency
        target_t60 = RoomTargets.get_target(room_type)
        schroeder = SchroederAnalyzer(
            mode_calc.volume, 
            (target_t60['t60_min'] + target_t60['t60_max']) / 2,
            use_metric
        )
        schroeder_analysis = schroeder.analyze()
        treatment_zones = schroeder.get_treatment_zones()
        
        # Calculate absorption requirements
        absorption_calc = AbsorptionCalculator(length, width, height, use_metric)
        absorption = absorption_calc.analyze(target_t60['t60_min'])
        
        return jsonify({
            "success": True,
            "room_report": report,
            "schroeder": {
                "frequency": schroeder_analysis.schroeder_frequency,
                "modal_density": schroeder_analysis.modal_density,
                "bass_trap_range": schroeder_analysis.bass_trap_range,
                "absorber_range": schroeder_analysis.absorber_range
            },
            "treatment_zones": treatment_zones,
            "absorption": {
                "current_t60": absorption.current_t60,
                "target_t60": absorption.target_t60,
                "missing_absorption": absorption.missing_absorption,
                "recommendations": absorption.recommended_treatment
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/upload-rew', methods=['POST'])
def upload_rew():
    """
    Upload and analyze REW measurement file.
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            "success": False, 
            "error": f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Parse REW file
        parser = REWParser()
        measurement = parser.parse_file(filepath)
        
        # Analyze measurement
        analyzer = REWAnalyzer(measurement)
        
        result = {
            "success": True,
            "filename": filename,
            "measurement_name": measurement.name
        }
        
        # Add frequency response analysis if available
        if measurement.frequency_response:
            fr = measurement.frequency_response
            result["frequency_response"] = {
                "frequencies": fr.frequencies.tolist(),
                "magnitudes": fr.magnitudes.tolist(),
                "frequency_range": fr.frequency_range,
                "average_level": fr.get_average_level()
            }
            result["fr_analysis"] = analyzer.analyze_frequency_response()
            result["modal_problems"] = analyzer.identify_modal_problems()
        
        # Clean up
        os.remove(filepath)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/generate-treatment-plan', methods=['POST'])
def generate_treatment_plan():
    """
    Generate a complete treatment plan.
    
    Expected JSON:
    {
        "length": float,
        "width": float,
        "height": float,
        "unit": "metric" | "imperial",
        "room_type": string,
        "current_t60": float (optional),
        "problem_frequencies": [float] (optional)
    }
    """
    data = request.get_json()
    
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        room_type = data.get('room_type', 'mixing_mastering')
        current_t60 = data.get('current_t60')
        problem_freqs = data.get('problem_frequencies', [])
        
        # Generate treatment plan
        engine = TreatmentRecommendationEngine(
            length, width, height, use_metric, room_type
        )
        plan = engine.generate_treatment_plan(
            current_t60=current_t60,
            measured_modes=problem_freqs
        )
        
        # Convert to JSON-serializable format
        plan_dict = {
            "room_type": plan.room_type,
            "target_t60": plan.target_t60,
            "items": [item.to_dict() for item in plan.get_by_priority()],
            "bill_of_materials": plan.get_bill_of_materials(),
            "notes": plan.notes,
            "estimated_cost": plan.estimated_total_cost
        }
        
        return jsonify({
            "success": True,
            "treatment_plan": plan_dict
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/speaker-placement', methods=['POST'])
def calculate_speaker_placement():
    """
    Calculate optimal speaker placement.
    
    Expected JSON:
    {
        "length": float,
        "width": float,
        "height": float,
        "unit": "metric" | "imperial",
        "speaker_type": "nearfield" | "midfield" | "main"
    }
    """
    data = request.get_json()
    
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        speaker_type = data.get('speaker_type', 'nearfield')
        
        # Calculate placement
        optimizer = SpeakerPlacementOptimizer(length, width, height, use_metric)
        report = optimizer.generate_placement_report(speaker_type)
        
        return jsonify({
            "success": True,
            "placement": report
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/design-panel', methods=['POST'])
def design_panel():
    """
    Design a specific acoustic panel.
    
    Expected JSON:
    {
        "panel_type": "broadband_absorber" | "corner_bass_trap" | "helmholtz_resonator" | "qrd_diffuser" | "membrane_absorber",
        "target_frequency": float (optional),
        "width": float,
        "height": float,
        "unit": "metric" | "imperial",
        "thickness": float (optional),
        "air_gap": float (optional),
        "material": string (optional),
        "design_frequency": float (optional),
        "prime_number": int (optional),
        "cavity_depth": float (optional),
        "membrane_material": string (optional)
    }
    """
    data = request.get_json()
    
    try:
        panel_type = data['panel_type']
        use_metric = data.get('unit', 'metric') == 'metric'
        
        # Convert to millimeters if metric (input is in meters)
        if use_metric:
            width = float(data.get('width', 0.6)) * 1000  # meters to mm
            height = float(data.get('height', 1.2)) * 1000  # meters to mm
        else:
            width = float(data.get('width', 24)) * 25.4  # inches to mm
            height = float(data.get('height', 48)) * 25.4  # inches to mm
        
        calculator = PanelConstructionCalculator(use_metric)
        
        if panel_type in ['broadband_absorber', 'broadband']:
            thickness = float(data.get('thickness', 100))
            material = data.get('material', 'rockwool')
            material_key = 'rockwool_60' if 'rockwool' in material else 'owens_703'
            panel = calculator.design_broadband_absorber(
                width=width, 
                height=height, 
                target_low_freq=int(data.get('target_frequency', 250)),
                material_key=material_key
            )
        elif panel_type in ['corner_bass_trap', 'bass_trap']:
            panel = calculator.design_corner_bass_trap(
                height=height,
                target_freq=int(data.get('target_frequency', 80))
            )
        elif panel_type in ['helmholtz_resonator', 'helmholtz']:
            target_freq = float(data.get('target_frequency', 80))
            panel = calculator.design_helmholtz_resonator(
                target_freq=target_freq,
                width=width,
                height=height
            )
        elif panel_type in ['qrd_diffuser', 'qrd']:
            prime = int(data.get('prime_number', data.get('prime', 7)))
            design_freq = float(data.get('design_frequency', data.get('target_frequency', 500)))
            panel = calculator.design_qrd_diffuser(
                prime=prime,
                design_freq=design_freq,
                width=width,
                height=height
            )
        elif panel_type in ['membrane_absorber', 'membrane']:
            target_freq = float(data.get('target_frequency', 100))
            panel = calculator.design_membrane_absorber(
                target_freq=target_freq,
                width=width,
                height=height
            )
        else:
            return jsonify({
                "success": False, 
                "error": f"Unknown panel type: {panel_type}"
            }), 400
        
        return jsonify({
            "success": True,
            "panel": panel.to_dict()
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/design-hybrid-panel', methods=['POST'])
def api_design_hybrid_panel():
    """
    Design a hybrid absorber/reflector panel using MLS patterns.
    
    Expected JSON:
    {
        "panel_width_mm": float (e.g., 1400),
        "panel_height_mm": float (e.g., 1800),
        "slat_width_mm": float (preferred slat width, e.g., 50),
        "slat_thickness_mm": float (e.g., 20),
        "absorber_depth_mm": float (e.g., 100),
        "layout": "horizontal_1d" | "vertical_1d" | "grid_2d",
        "generate_inverse": bool
    }
    """
    data = request.get_json()
    
    try:
        panel_width_mm = float(data.get('panel_width_mm', 1400))
        panel_height_mm = float(data.get('panel_height_mm', 1800))
        slat_width_mm = float(data.get('slat_width_mm', 50))
        slat_thickness_mm = float(data.get('slat_thickness_mm', 20))
        absorber_depth_mm = float(data.get('absorber_depth_mm', 100))
        layout = data.get('layout', 'horizontal_1d')
        generate_inverse = data.get('generate_inverse', True)
        
        result = design_hybrid_panel(
            panel_width_mm=panel_width_mm,
            panel_height_mm=panel_height_mm,
            preferred_slat_width_mm=slat_width_mm,
            slat_thickness_mm=slat_thickness_mm,
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
    """Get all available MLS orders and their properties."""
    try:
        orders = get_all_mls_orders()
        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/quick-analysis', methods=['POST'])
def quick_analysis():
    """
    Quick room analysis returning key metrics and recommendations.
    """
    data = request.get_json()
    
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
        use_metric = data.get('unit', 'metric') == 'metric'
        room_type = data.get('room_type', 'mixing_mastering')
        
        recommendations = generate_quick_recommendations(
            length, width, height, room_type, use_metric
        )
        
        speaker = quick_speaker_placement(length, width, height, use_metric)
        
        return jsonify({
            "success": True,
            "analysis": recommendations,
            "speaker_placement": speaker
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/magic-analysis', methods=['POST'])
def magic_analysis_api():
    """
    Complete comprehensive room analysis - everything in one call.
    
    Accepts multipart/form-data with:
    - length, width, height, unit, room_type, speaker_type
    - rew_file (optional): REW measurement file or screenshot
    """
    try:
        # Parse form data
        length = float(request.form['length'])
        width = float(request.form['width'])
        height = float(request.form['height'])
        use_metric = request.form.get('unit', 'metric') == 'metric'
        room_type = request.form.get('room_type', 'mixing_mastering')
        speaker_type = request.form.get('speaker_type', 'nearfield')
        
        unit_label = 'metric' if use_metric else 'imperial'
        
        # Calculate room modes
        mode_calc = RoomModeCalculator(length, width, height, use_metric)
        modes_data = mode_calc.calculate_all_modes(max_frequency=300)
        bonello = mode_calc.bonello_analysis()
        
        # Calculate Schroeder frequency
        volume = length * width * height
        # Estimate T60 based on room type (typical untreated room)
        estimated_t60 = 0.5  # 500ms for untreated room
        schroeder_calc = SchroederAnalyzer(volume, estimated_t60, use_metric)
        schroeder = schroeder_calc.analyze()
        
        # Room ratios
        ratios_data = mode_calc.get_optimal_ratios()
        ratios = ratios_data['current_ratios']
        # Get quality of best match
        ratio_quality = ratios_data['comparisons'][ratios_data['best_match']]['match_quality']
        
        # Target T60
        target_t60_map = {
            'mixing_mastering': '200-250',
            'recording': '250-300',
            'music_production': '200-300',
            'home_theater': '300-400'
        }
        target_t60 = target_t60_map.get(room_type, '200-300')
        
        # Process REW file if uploaded
        rew_data = None
        rew_file = request.files.get('rew_file')
        if rew_file and rew_file.filename:
            filename = secure_filename(rew_file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            if ext in ['png', 'jpg', 'jpeg']:
                # Image upload - add note that we accept it but can't parse yet
                rew_data = {
                    'is_image': True,
                    'message': 'Image upload detected. For best results, export REW data as .txt or .mdat file.',
                    'frequencies': [],
                    'magnitude': [],
                    'peaks': [],
                    'dips': [],
                    'problem_frequencies': []
                }
            elif ext in ALLOWED_EXTENSIONS:
                # Parse REW file
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                rew_file.save(filepath)
                
                try:
                    parser = REWParser()
                    measurement = parser.parse(filepath)
                    analyzer = REWAnalyzer(measurement)
                    analysis = analyzer.analyze()
                    
                    rew_data = {
                        'is_image': False,
                        'frequencies': measurement.frequency_response.frequencies[:1000].tolist(),  # Limit data
                        'magnitude': measurement.frequency_response.magnitude[:1000].tolist(),
                        'peaks': [{'freq': p['frequency'], 'mag': p['magnitude']} for p in analysis['peaks'][:10]],
                        'dips': [{'freq': d['frequency'], 'mag': d['magnitude']} for d in analysis['dips'][:10]],
                        'problem_frequencies': analysis['problem_frequencies'][:10]
                    }
                    
                    # Clean up temp file
                    os.remove(filepath)
                except Exception as e:
                    rew_data = {
                        'error': f'Could not parse REW file: {str(e)}',
                        'frequencies': [],
                        'magnitude': [],
                        'peaks': [],
                        'dips': [],
                        'problem_frequencies': []
                    }
        
        # Generate treatment plan
        engine = TreatmentRecommendationEngine(length, width, height, use_metric, room_type)
        problem_freqs = []
        if rew_data and 'problem_frequencies' in rew_data:
            problem_freqs = rew_data['problem_frequencies']
        plan = engine.generate_treatment_plan(measured_modes=problem_freqs)
        
        # Speaker placement
        optimizer = SpeakerPlacementOptimizer(length, width, height, use_metric)
        speaker_report = optimizer.generate_placement_report(speaker_type)
        
        # Generate DIY panel designs for the main treatment items
        calculator = PanelConstructionCalculator(use_metric)
        diy_panels = []
        
        # Bass trap
        try:
            bass_trap = calculator.design_corner_bass_trap(height=height, target_low_freq=60)
            diy_panels.append({
                'type': 'corner_bass_trap',
                'specifications': bass_trap.specifications,
                'performance': bass_trap.performance,
                'materials': bass_trap.materials,
                'construction_steps': bass_trap.construction_steps,
                'tips': bass_trap.tips
            })
        except:
            pass
        
        # Broadband absorber
        try:
            absorber = calculator.design_broadband_absorber(
                width=600 if use_metric else 24,
                height=1200 if use_metric else 48,
                target_low_freq=250
            )
            diy_panels.append({
                'type': 'broadband_absorber',
                'specifications': absorber.specifications,
                'performance': absorber.performance,
                'materials': absorber.materials,
                'construction_steps': absorber.construction_steps,
                'tips': absorber.tips
            })
        except:
            pass
        
        # QRD Diffuser
        try:
            diffuser = calculator.design_qrd_diffuser(
                prime=7,
                design_freq=500,
                width=600 if use_metric else 24,
                height=600 if use_metric else 24
            )
            diy_panels.append({
                'type': 'qrd_diffuser',
                'specifications': diffuser.specifications,
                'performance': diffuser.performance,
                'materials': diffuser.materials,
                'construction_steps': diffuser.construction_steps,
                'tips': diffuser.tips
            })
        except:
            pass
        
        # Compile complete response
        response = {
            'success': True,
            'unit': unit_label,
            'room': {
                'length': length,
                'width': width,
                'height': height,
                'unit': unit_label,
                'volume': round(volume, 2),
                'schroeder_frequency': round(schroeder.schroeder_frequency, 1),
                'target_t60': target_t60,
                'ratios': ratios,
                'ratio_quality': ratio_quality
            },
            'modes': {
                'modes': [
                    {
                        'frequency': round(m.frequency, 1),
                        'type': m.mode_type.name.capitalize(),
                        'indices': m.mode_string
                    }
                    for m in modes_data[:50]  # Limit to first 50
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
                    {
                        'item': mat_data['material'],
                        'quantity': mat_data['count'],
                        'unit': 'panels',
                        'notes': f"Total area: {mat_data['total_area']:.2f} sq {'m' if use_metric else 'ft'}"
                    }
                    for mat_key, mat_data in plan.get_bill_of_materials().items()
                ],
                'notes': plan.notes
            },
            'diy_panels': diy_panels
        }
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        return jsonify({
            "success": False, 
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 400


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
