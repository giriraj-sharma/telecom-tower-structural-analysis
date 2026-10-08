import math
from typing import List, Dict, Tuple, Any
from app.models.schemas import TowerInput, GeometryNode, GeometryMember

class PanelGeometry:
    def __init__(self, index: int, z_bottom: float, z_top: float, width_bottom: float, width_top: float):
        self.index = index
        self.z_bottom = z_bottom
        self.z_top = z_top
        self.height = z_top - z_bottom
        self.z_mid = (z_bottom + z_top) / 2.0
        self.width_bottom = width_bottom
        self.width_top = width_top
        self.width_mid = (width_bottom + width_top) / 2.0

class TowerGeometryBuilder:
    def __init__(self, params: TowerInput):
        self.params = params
        self.height = params.height_m
        self.base_width = params.base_width_m
        self.top_width = params.top_width_m
        self.tower_type = params.tower_type
        self.bracing_type = params.bracing_type
        
        # Calculate panels
        nominal_panel_h = params.panel_height_m
        self.num_panels = max(3, round(self.height / nominal_panel_h))
        self.panel_height = self.height / self.num_panels
        
        self.panels: List[PanelGeometry] = []
        for i in range(self.num_panels):
            z_b = i * self.panel_height
            z_t = (i + 1) * self.panel_height
            w_b = self.width_at_height(z_b)
            w_t = self.width_at_height(z_t)
            self.panels.append(PanelGeometry(i, z_b, z_t, w_b, w_t))
            
    def width_at_height(self, z: float) -> float:
        ratio = max(0.0, min(1.0, z / self.height))
        return self.base_width + (self.top_width - self.base_width) * ratio

    def generate_mesh(self) -> Tuple[List[GeometryNode], List[GeometryMember], Dict[str, Any]]:
        nodes: List[GeometryNode] = []
        members: List[GeometryMember] = []
        node_map: Dict[Tuple[int, int], int] = {} # (level, leg_index) -> node_id
        
        node_id_counter = 0
        num_legs = 3 if self.tower_type == "3-leg" else 4
        
        # Generate nodes level by level
        for lvl in range(self.num_panels + 1):
            z = lvl * self.panel_height
            w = self.width_at_height(z)
            
            if self.tower_type == "3-leg":
                # Equilateral triangle
                radius = w / math.sqrt(3.0)
                # Angle offsets for 120-degree symmetry: 90 deg, 210 deg, 330 deg
                angles = [math.pi / 2.0, math.pi / 2.0 + 2.0 * math.pi / 3.0, math.pi / 2.0 + 4.0 * math.pi / 3.0]
                for leg_idx in range(3):
                    ang = angles[leg_idx]
                    x = radius * math.cos(ang)
                    y = radius * math.sin(ang)
                    nodes.append(GeometryNode(id=node_id_counter, x=round(x, 4), y=round(y, 4), z=round(z, 4)))
                    node_map[(lvl, leg_idx)] = node_id_counter
                    node_id_counter += 1
            else:
                # 4-leg square tower
                half_w = w / 2.0
                corners = [
                    (-half_w, -half_w),
                    (half_w, -half_w),
                    (half_w, half_w),
                    (-half_w, half_w)
                ]
                for leg_idx in range(4):
                    x, y = corners[leg_idx]
                    nodes.append(GeometryNode(id=node_id_counter, x=round(x, 4), y=round(y, 4), z=round(z, 4)))
                    node_map[(lvl, leg_idx)] = node_id_counter
                    node_id_counter += 1

        # Generate members per panel
        total_leg_length = 0.0
        total_diagonal_length = 0.0
        total_horizontal_length = 0.0

        for p_idx in range(self.num_panels):
            lvl_b = p_idx
            lvl_t = p_idx + 1
            
            # 1. Leg members
            for leg_idx in range(num_legs):
                n_start = node_map[(lvl_b, leg_idx)]
                n_end = node_map[(lvl_t, leg_idx)]
                members.append(GeometryMember(
                    id=f"LEG_P{p_idx+1}_L{leg_idx+1}",
                    type="leg",
                    start_node=n_start,
                    end_node=n_end,
                    utilization=0.0,
                    status="SAFE"
                ))
                dx = nodes[n_end].x - nodes[n_start].x
                dy = nodes[n_end].y - nodes[n_start].y
                dz = nodes[n_end].z - nodes[n_start].z
                total_leg_length += math.sqrt(dx*dx + dy*dy + dz*dz)

            # 2. Horizontals at top of panel
            for leg_idx in range(num_legs):
                next_leg = (leg_idx + 1) % num_legs
                n_start = node_map[(lvl_t, leg_idx)]
                n_end = node_map[(lvl_t, next_leg)]
                members.append(GeometryMember(
                    id=f"HORIZ_P{p_idx+1}_F{leg_idx+1}",
                    type="horizontal",
                    start_node=n_start,
                    end_node=n_end,
                    utilization=0.0,
                    status="SAFE"
                ))
                dx = nodes[n_end].x - nodes[n_start].x
                dy = nodes[n_end].y - nodes[n_start].y
                dz = nodes[n_end].z - nodes[n_start].z
                total_horizontal_length += math.sqrt(dx*dx + dy*dy + dz*dz)

            # 3. Diagonals on each face
            for leg_idx in range(num_legs):
                next_leg = (leg_idx + 1) % num_legs
                b_curr = node_map[(lvl_b, leg_idx)]
                b_next = node_map[(lvl_b, next_leg)]
                t_curr = node_map[(lvl_t, leg_idx)]
                t_next = node_map[(lvl_t, next_leg)]
                
                if self.bracing_type == "X-brace":
                    # Cross diagonals
                    members.append(GeometryMember(
                        id=f"DIAG_P{p_idx+1}_F{leg_idx+1}_A",
                        type="diagonal",
                        start_node=b_curr,
                        end_node=t_next,
                        utilization=0.0,
                        status="SAFE"
                    ))
                    members.append(GeometryMember(
                        id=f"DIAG_P{p_idx+1}_F{leg_idx+1}_B",
                        type="diagonal",
                        start_node=b_next,
                        end_node=t_curr,
                        utilization=0.0,
                        status="SAFE"
                    ))
                    # lengths
                    d1 = math.sqrt((nodes[t_next].x - nodes[b_curr].x)**2 + (nodes[t_next].y - nodes[b_curr].y)**2 + (nodes[t_next].z - nodes[b_curr].z)**2)
                    d2 = math.sqrt((nodes[t_curr].x - nodes[b_next].x)**2 + (nodes[t_curr].y - nodes[b_next].y)**2 + (nodes[t_curr].z - nodes[b_next].z)**2)
                    total_diagonal_length += d1 + d2
                elif self.bracing_type == "Warren":
                    # Alternating single diagonal
                    if p_idx % 2 == 0:
                        start_n, end_n = b_curr, t_next
                    else:
                        start_n, end_n = b_next, t_curr
                    members.append(GeometryMember(
                        id=f"DIAG_P{p_idx+1}_F{leg_idx+1}",
                        type="diagonal",
                        start_node=start_n,
                        end_node=end_n,
                        utilization=0.0,
                        status="SAFE"
                    ))
                    diag_len = math.sqrt((nodes[end_n].x - nodes[start_n].x)**2 + (nodes[end_n].y - nodes[start_n].y)**2 + (nodes[end_n].z - nodes[start_n].z)**2)
                    total_diagonal_length += diag_len
                elif self.bracing_type == "K-brace":
                    # Mid-point on horizontal or chevron pattern
                    members.append(GeometryMember(
                        id=f"DIAG_P{p_idx+1}_F{leg_idx+1}_A",
                        type="diagonal",
                        start_node=b_curr,
                        end_node=t_next,
                        utilization=0.0,
                        status="SAFE"
                    ))
                    members.append(GeometryMember(
                        id=f"DIAG_P{p_idx+1}_F{leg_idx+1}_B",
                        type="diagonal",
                        start_node=b_next,
                        end_node=t_curr,
                        utilization=0.0,
                        status="SAFE"
                    ))
                    d1 = math.sqrt((nodes[t_next].x - nodes[b_curr].x)**2 + (nodes[t_next].y - nodes[b_curr].y)**2 + (nodes[t_next].z - nodes[b_curr].z)**2)
                    total_diagonal_length += d1 * 2

        summary = {
            "num_legs": num_legs,
            "num_faces": num_legs,
            "num_panels": self.num_panels,
            "panel_height": self.panel_height,
            "total_leg_length_m": total_leg_length,
            "total_diagonal_length_m": total_diagonal_length,
            "total_horizontal_length_m": total_horizontal_length,
            "node_count": len(nodes),
            "member_count": len(members)
        }
        return nodes, members, summary
