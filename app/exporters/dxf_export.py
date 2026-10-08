import io
import ezdxf
from ezdxf import colors
from app.models.schemas import AnalysisOutput, TowerInput

def generate_dxf_geometry(analysis: AnalysisOutput, tower_input: TowerInput) -> str:
    """
    Generates an AutoCAD-compatible 3D DXF file with dedicated layers for legs, braces, horizontals, and appurtenances.
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    
    # Setup CAD Layers with standard ACI colors
    layers = [
        ("TOWER_LEGS", colors.GREEN, "Continuous"),
        ("TOWER_DIAGONALS", colors.CYAN, "Continuous"),
        ("TOWER_HORIZONTALS", colors.YELLOW, "Continuous"),
        ("ANTENNAS_EQUIPMENT", colors.RED, "Continuous"),
        ("FOUNDATION_GRID", colors.GRAY, "Continuous"),
        ("ANNOTATIONS", colors.WHITE, "Continuous")
    ]
    
    for name, col, linetype in layers:
        if name not in doc.layers:
            doc.layers.add(name=name, color=col, linetype=linetype)
            
    # Node lookup: id -> (x, y, z)
    node_map = {n.id: (n.x, n.y, n.z) for n in analysis.nodes}
    
    # Draw Structural Members
    for m in analysis.members:
        start_pt = node_map.get(m.start_node)
        end_pt = node_map.get(m.end_node)
        
        if not start_pt or not end_pt:
            continue
            
        layer_name = "TOWER_LEGS" if m.type == "leg" else ("TOWER_DIAGONALS" if m.type == "diagonal" else "TOWER_HORIZONTALS")
        msp.add_line(start_pt, end_pt, dxfattribs={"layer": layer_name})

    # Draw Foundation Base Pad Grid
    b_half = tower_input.base_width_m / 2.0
    pad_offset = 0.8
    p1 = (-b_half - pad_offset, -b_half - pad_offset, 0.0)
    p2 = (b_half + pad_offset, -b_half - pad_offset, 0.0)
    p3 = (b_half + pad_offset, b_half + pad_offset, 0.0)
    p4 = (-b_half - pad_offset, b_half + pad_offset, 0.0)
    
    msp.add_lwpolyline([p1[:2], p2[:2], p3[:2], p4[:2]], close=True, dxfattribs={"layer": "FOUNDATION_GRID", "elevation": 0.0})
    
    # Draw Antenna Appurtenances representation
    for eq in tower_input.equipment_items:
        z = eq.elevation_m
        # Draw a ring or box at antenna elevation
        radius = 0.6
        msp.add_circle(center=(0.0, 0.0, z), radius=radius, dxfattribs={"layer": "ANTENNAS_EQUIPMENT"})
        msp.add_text(
            f"{eq.name} (Qty {eq.quantity}) @ EL+{z:.1f}m",
            dxfattribs={"layer": "ANNOTATIONS", "height": 0.35}
        ).set_placement((radius + 0.3, 0.0, z))

    # Add Overall Tower Dimensions and Title Annotations
    msp.add_text(
        f"TELECOM LATTICE TOWER - H={tower_input.height_m:.1f}m ({tower_input.tower_type.upper()})",
        dxfattribs={"layer": "ANNOTATIONS", "height": 0.8}
    ).set_placement((-b_half, -b_half - 2.5, 0.0))
    
    msp.add_text(
        f"Base Width: {tower_input.base_width_m:.1f}m | Top Width: {tower_input.top_width_m:.1f}m | Wind: {tower_input.wind_speed_kmh} km/h",
        dxfattribs={"layer": "ANNOTATIONS", "height": 0.45}
    ).set_placement((-b_half, -b_half - 3.5, 0.0))

    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()
