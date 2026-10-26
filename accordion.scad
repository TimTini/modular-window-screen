// V4.2: automatic even-leaf span and repeated threaded extensions, 430..1000 mm.
// Every printed part stays within 250 mm.
use <threads.scad>
part="display";
W=620;
H=250; // Leaf, both end supports and the pin use the 250 mm bed.
clamp_travel=0;
assert(clamp_travel>=0 && clamp_travel<=75,
       "Clamp travel must be 0..75 mm");
assembly_span=W-clamp_travel;
$fn=48;
pitch=42;
hinge_bore_r=2.3;
hinge_outer_r=4.6;
hinge_min_wall=2;
support_ear_bottom=-14;
support_trim_margin=0.3;
assert(support_trim_margin>=0,"Support trim margin must be nonnegative");
leaf_bottom=-4.5;
leaf_top=4.5;
leaf_thickness=leaf_top-leaf_bottom; // Match the actual flat-bottom hinge tube height.
assert(min(leaf_top,-leaf_bottom,hinge_outer_r*cos(180/$fn))-hinge_bore_r >= hinge_min_wall,
       "Hinge wall contract must be at least 2 mm");
// W changes the even leaf/pin quantities and the printed left-support length.
// Changing W can therefore require reprinting those parts; this is not a claim
// that every intermediate width has been physically validated.
leaf_count=2*ceil((W-20)/(2*(pitch-2)));
clearance=0.3;
pip_gap=0.6;
right_ring_min_wall=2;
right_ring_wall_margin=0.2;
support_web_width=10;
assert(support_web_width>=10,"Support web must reach the end plate");
rotor_outer_r=18;
rotor_waist_r=10.5;
capture_center_x=-3;
capture_width=8;
female_foot_width=9;
thread_socket_outer_r=16;
socket_max_r=rotor_waist_r+capture_width/2+pip_gap;
right_axis_z=socket_max_r+right_ring_min_wall+right_ring_wall_margin;
right_print_lift=30+right_axis_z;
assert(20*cos(180/48)-socket_max_r>=right_ring_min_wall,
       "Ring radial wall below 2 mm");
assert(right_axis_z-socket_max_r>=right_ring_min_wall,
       "Ring bottom wall below 2 mm");
assert(rotor_outer_r>right_axis_z,"Rotor body must meet the bed");
joint_angle=0;
thread_offset=-0.25; // Signed FDM allowance applied to both mating threads.
male_bore_d=2; // User-tunable empty axial passage through every male thread.
male_bore_r=male_bore_d/2;
assert(male_bore_d>0,"Male axial bore diameter must be positive");
socket_depth=25;
tip_thread=110;
max_extension_length=230;
max_male_length=240;
phase_tolerance=1e-6;
extension_count=max(1,ceil((W-120-max_male_length)/(max_extension_length-socket_depth)));
male_length=max(175,W-120-extension_count*(max_extension_length-socket_depth));
extension_length=socket_depth+(W-120-male_length)/extension_count;
shank=extension_length-tip_thread;
function extension_start(i)=10+male_length-socket_depth+i*(extension_length-socket_depth);
function extension_turn(i)=(extension_start(i)-10-i*shank)/4;
tip_start=extension_start(extension_count-1)+shank;
male_tip=extension_start(extension_count-1)+extension_length;
final_female_turn=((W-140)-10-extension_count*shank)/4;
dx=(assembly_span-20)/leaf_count;
dz=sqrt(pitch*pitch-dx*dx);
assert(W>=430 && W<=1000,"W must be 430..1000 mm");
assert(extension_count>=1 && extension_count==floor(extension_count),
       "Extension count must be a positive integer");
assert(extension_length>=160 && extension_length<=max_extension_length,
       "Extension length must be 160..230 mm");
assert(male_length>=175 && male_length<=max_male_length,
       "Male length must be 175..240 mm");
assert(shank>=socket_depth+25,"Extension shank must leave a 25 mm reserve");
assert(extension_length<=250 && male_length+10<=250,
       "Rod pieces must fit the 250 mm bed");
assert(dx<pitch,"Leaves cannot reach a straight line inside this width range");
tip_overlap=male_tip-(W-140);
shoulder_clearance=(W-140)-tip_start;
actual_female_engagement=tip_overlap+clamp_travel;
actual_shoulder_gap=shoulder_clearance-clamp_travel;
assert(abs(tip_overlap-30)<phase_tolerance,
       "Last male engagement must be 30 mm");
assert(shoulder_clearance>=80-phase_tolerance,
       "Terminal shoulder clearance must be at least 80 mm");
assert(actual_female_engagement<=118+phase_tolerance,
       "Actual female engagement must be at most 118 mm");
assert(actual_shoulder_gap>=5-phase_tolerance,
       "Actual shoulder gap must be at least 5 mm");
if(extension_count>1) for(i=[0:extension_count-2]) {
    assert(abs((extension_start(i+1)-extension_start(i))-
               (extension_length-socket_depth))<phase_tolerance,
           "Adjacent extension sockets must overlap by 25 mm");
    assert(abs((extension_turn(i+1)-extension_turn(i))-21.25)<phase_tolerance,
           "Adjacent extension phase step must be 21.25 turns");
}
assert(abs(final_female_turn-extension_turn(extension_count-1)-20)<phase_tolerance,
       "Final female phase must be 20 turns after the last extension");
echo(leaf_count=leaf_count, pin_count=leaf_count+1, width_mm=W,
     male_length_mm=male_length, extension_count=extension_count,
     extension_length_mm=extension_length, clamp_travel_mm=clamp_travel,
     assembly_span_mm=assembly_span);
pin_head=3;
pin_neck=0.5;
assert(H==250,"Prototype height is 250 mm");
assert(H%25==0,"Height must be a multiple of 25 mm");
function band_count(h)=h/25;
function band_y(j)=j*25+clearance/2;
// The pin head occupies the last pin_head millimetres. The neck cone starts
// pin_neck earlier, so the knuckle stops there instead of cutting into the cone.
function band_len(j,h)=min(25-clearance,h-pin_head-pin_neck-band_y(j));
assert(pip_gap>=0.4 && pip_gap<=0.9,"PIP radial gap must be 0.4..0.9 mm");
function point(i)=[10+i*dx,0,i%2?dz:0];
function slope(i)=(i%2?-1:1)*atan2(dz,dx);
module cy_y(r,h,n=$fn) {rotate([-90,0,0]) cylinder(r=r,h=h,$fn=n);}
module cy_x(r,h,n=$fn) {rotate([0,90,0]) cylinder(r=r,h=h,$fn=n);}
module knuckles(parity,h=H) {
    difference() {
        for(j=[0:band_count(h)-1]) if(j%2==parity && band_len(j,h)>0)
            translate([0,band_y(j),0]) cy_y(hinge_outer_r,band_len(j,h));
        translate([0,-1,0]) cy_y(hinge_bore_r,h+2);
    }
}
// Relieve the moving leaf's bands; the support's own knuckles occupy the other parity.
module hinge_sweep_clearance(parity,h=H) {
    for(j=[0:band_count(h)-1]) if(j%2==parity && band_len(j,h)>0)
        translate([0,band_y(j)-clearance/2,0])
            cy_y(hinge_outer_r+clearance,band_len(j,h)+clearance);
}
// One-piece flat leaf: circular working bore, clipped barrel, common bed plane.
module leaf_barrel(h) {
    intersection() {
        cy_y(hinge_outer_r,h);
        translate([-hinge_outer_r,0,leaf_bottom])
            cube([2*hinge_outer_r,h,leaf_thickness]);
    }
}
module leaf(h=H) {
    assert(h>=25 && h%25==0,"Leaf height must be a positive multiple of 25 mm");
    difference() {
        union() {
            translate([6,0,leaf_bottom]) cube([pitch-12,h,leaf_thickness]);
            for(j=[0:band_count(h)-1]) if(band_len(j,h)>0) {
                edge=j%2;
                y=band_y(j);
                translate([edge?pitch:0,y,0]) leaf_barrel(band_len(j,h));
                // Full-width rectangular connector; square shoulders for flat printing.
                translate([edge?pitch-6:0,y,leaf_bottom])
                    cube([6,band_len(j,h),leaf_thickness]);
            }
        }
        for(x=[0,pitch]) translate([x,-1,0]) cy_y(hinge_bore_r,h+2);
    }
}
module print_leaf(h=H) {translate([hinge_outer_r,0,-leaf_bottom]) leaf(h);}
module short_hinge_pin() {
    difference() {
        union() {cylinder(r=2,h=51);translate([0,0,51])cylinder(r=4,h=3);}
        translate([1.5,-5,-1])cube([5,10,56]);
    }
}
module fit_kit() {
    // Two one-piece 50 mm leaves and one shared short pin.
    for(i=[0:1]) translate([55*i,0,0]) print_leaf(50);
    translate([0,60,1.5])rotate([0,90,0])short_hinge_pin();
}
module three_leaves() {
    for(i=[0:2]) color(i%2?"#82bca3":"#b4d3b7") placed_leaf(i);
    for(i=[1:2]) color("#e5a25d") placed_pin(i);
}
module hinge_pin() {
    difference() {
        union() {
            cylinder(r=2,h=H-pin_head);
            translate([0,0,H-pin_head-pin_neck]) cylinder(r1=2,r2=4,h=pin_neck);
            translate([0,0,H-pin_head]) cylinder(r=4,h=pin_head);
        }
        // A shallow D-flat gives the long pin a stable bed contact when laid down.
        translate([1.5,-5,-1]) cube([5,10,H+2]);
    }
}
module end_plate(side) {
    difference() {
        union() {
            translate([side<0?-10:4,0,-8]) cube([6,H,leaf_top+8]);
            // A single polygonal extrusion keeps the pin ear integral with the
            // full height spine while retaining the circular hinge bore.
            for(j=[0:band_count(H)-1])
                if(j%2==(side<0?1:0) && band_len(j,H)>0)
                    translate([0,band_y(j)+band_len(j,H),0]) rotate([90,0,0])
                        linear_extrude(band_len(j,H)) polygon([for(p=[
                            [-10,support_ear_bottom],[-4.5,support_ear_bottom],[0,-9.5],[0,-9.2],
                            [4.6,-4.6],[4.6,1.6],[1.6,4.6],[-10,4.6]]) [-side*p[0],p[1]]]);
        }
        translate([0,-1,0]) cy_y(hinge_bore_r,H+2);
    }
}
module support_web(side,foot_z) {
    // Shared mirrored spine; each attachment keeps its grounded bed plane.
    bed_z=side<0?-38:-right_print_lift;
    web_height=-5-bed_z;
    trim_height=-bed_z+support_ear_bottom-support_trim_margin;
    web_origin=side<0?-support_web_width:0;
    web_width=support_web_width;
    assert(trim_height>0,"Support trim height must be positive");
    assert(2*trim_height<H,"Support trim height must leave a hinge span");
    assert(trim_height<web_height,"Support trim must stay below the web top");
    // Keep the exact-width grounded cube and remove only the two lower end
    // wedges.  The cutters overrun X so their Boolean seam stays away from
    // the support's coplanar end faces.
    difference() {
        translate([web_origin,0,bed_z]) cube([web_width,H,web_height]);
        translate([web_origin-1,0,bed_z]) rotate([90,0,90])
            linear_extrude(height=web_width+2)
                polygon([[-1,-1],[trim_height+1,-1],[-1,trim_height+1]]);
        translate([web_origin-1,H,bed_z]) rotate([90,0,90])
            linear_extrude(height=web_width+2)
                polygon([[1,-1],[-trim_height-1,-1],[1,trim_height+1]]);
    }
    // Spread the screw reaction over a 64 mm hinge-spine span; keep clamp faces fixed.
    // The web retains a 0.4 mm offset from the R4.6 barrel envelope; local relief keeps
    // the moving barrel clear without changing the clamp faces.
    if(side<0) {
        translate([-10,H/2-18,foot_z]) cube([10,36,-5-foot_z]);
        hull() {
            translate([-10,H/2-18,foot_z]) cube([10,36,8]);
            translate([-10,H/2-32,-12]) cube([6,64,6]);
        }
    }
}
module left_support() {
    // Integral root and rear web eliminate a loose anti-rotation adapter.
    intersection() {
        difference() {
            union() {
                end_plate(-1);
                translate([-10,H/2-12,-38]) cube([8,24,34]);
                support_web(-1,-38);
                translate([-4,H/2,-30]) cy_x(8,6);
                translate([0,H/2,-30]) rotate([0,90,0]) male_thread(male_length,thread_offset);
                // Sole joins the threaded root to the print bed.
                translate([0,H/2-0.5,-38]) cube([male_length,1,1.5]);
            }
            // Start behind the rear body and continue through the complete male length.
            translate([-support_web_width-0.1,H/2,-30]) rotate([0,90,0])
                cylinder(r=male_bore_r,h=male_length+support_web_width+0.2,$fn=128);
            translate([0,-1,0]) cy_y(hinge_bore_r,H+2);
            hinge_sweep_clearance(0);
        }
        translate([-200,-100,-38]) cube([600,500,350]);
    }
}
module pip_void() {
    groove_half=rotor_outer_r-rotor_waist_r;
    groove_start=capture_center_x-groove_half;
    groove_end=capture_center_x+groove_half;
    exit_x=max(groove_end+5.1,support_web_width+0.1);
    // Match the rotor's V shoulders and extend clearance past the ring entry.
    translate([0,H/2,-30]) rotate([0,90,0]) rotate_extrude($fn=128)
        polygon([[0,groove_start-0.1],
                 [rotor_outer_r+pip_gap+0.1,groove_start-0.1],
                 [rotor_outer_r+pip_gap,groove_start],
                 [rotor_waist_r+pip_gap,capture_center_x],
                 [rotor_outer_r+pip_gap,groove_end],
                 [rotor_outer_r+pip_gap,exit_x],
                 [0,exit_x]]);
}
module right_support() {
    intersection() {
        difference() {
            union() {
                end_plate(1);
                translate([capture_center_x-capture_width/2,H/2,-30])
                    cy_x(20,capture_width);
                support_web(1,-26);
            }
            pip_void();
            translate([0,-1,0]) cy_y(hinge_bore_r,H+2);
            hinge_sweep_clearance(1);
        }
        translate([-200,-100,-right_print_lift]) cube([600,500,350]);
    }
}
female_profile_r=thread_socket_outer_r;
female_profile_floor=-right_axis_z;
female_profile_half_foot=female_foot_width/2;
female_profile_c=right_axis_z+female_profile_half_foot;
profile_discriminant=2*female_profile_r*female_profile_r-
                     female_profile_c*female_profile_c;
female_profile_join_z=(-female_profile_c+sqrt(profile_discriminant))/2;
female_profile_join_y=female_profile_join_z+female_profile_c;
female_profile_join_angle=atan2(female_profile_join_z,female_profile_join_y);
assert(female_foot_width>0,"Female foot width must be positive");
assert(profile_discriminant>=0,"Female profile join discriminant must be nonnegative");
assert(female_profile_join_y>female_profile_half_foot &&
       female_profile_join_z>female_profile_floor,
       "Female profile join must clear its foot");
assert(female_profile_c/sqrt(2)-rotor_waist_r>2,
       "Female lower 45 degree wall must exceed 2 mm");
assert(female_profile_half_foot*female_profile_half_foot+
       female_profile_floor*female_profile_floor<=rotor_outer_r*rotor_outer_r,
       "Female foot exceeds the old rotation envelope");
module female_body_profile(length) {
    assert(length>0,"Female body profile length must be positive");
    profile_arc_step=360/128;
    profile_arc_start=ceil(female_profile_join_angle/profile_arc_step)*profile_arc_step;
    profile_arc_end=floor((180-female_profile_join_angle)/profile_arc_step)*profile_arc_step;
    profile_angles=concat(
        [female_profile_join_angle],
        [for(angle=[profile_arc_start:profile_arc_step:profile_arc_end]) angle],
        [180-female_profile_join_angle]
    );
    profile_points=concat(
        [[-female_profile_half_foot,female_profile_floor],
         [female_profile_half_foot,female_profile_floor]],
        [for(angle=profile_angles)
            [female_profile_r*cos(angle),female_profile_r*sin(angle)]]
    );
    multmatrix([[0,0,1,0],[1,0,0,0],[0,1,0,0],[0,0,0,1]])
        linear_extrude(height=length,convexity=10)
        polygon(points=profile_points);
}
module female_body_transition(body_end,groove_start) {
    // Short caps keep the hull closed and overlap the first V shoulder.
    hull() {
        translate([body_end,H/2,-30]) female_body_profile(0.1);
        intersection() {
            translate([groove_start-0.1,H/2,-30]) cy_x(rotor_outer_r,0.1,128);
            translate([-200,-100,-right_print_lift]) cube([600,500,350]);
        }
    }
}
module female_rotor() {
    groove_half=rotor_outer_r-rotor_waist_r;
    groove_start=capture_center_x-groove_half;
    groove_end=capture_center_x+groove_half;
    female_body_end=groove_start-4;
    rotor_end=groove_end+5;
    difference() {
        union() {
            translate([-130,H/2,-30]) female_body_profile(female_body_end+130);
            female_body_transition(female_body_end,groove_start);
            intersection() {
                union() {
                    translate([groove_start,H/2,-30]) rotate([0,90,0])
                        cylinder(r1=rotor_outer_r,r2=rotor_waist_r,h=groove_half,$fn=128);
                    translate([capture_center_x,H/2,-30]) rotate([0,90,0])
                        cylinder(r1=rotor_waist_r,r2=rotor_outer_r,h=groove_half,$fn=128);
                    translate([groove_end,H/2,-30]) cy_x(rotor_outer_r,5,128);
                }
                translate([-200,-100,-right_print_lift]) cube([600,500,350]);
            }
        }
        // Preserve the source phase: the helical female groove starts at x=-130.
        translate([-130,H/2,-30]) rotate([0,90,0]) female_groove(118,thread_offset);
        translate([-130.1,H/2,-30]) cy_x(female_bore_r(),rotor_end+130.2,128);
    }
}
module right_pip() {
    union() {
        right_support();
        female_rotor();
    }
}
module pip_coupon() {
    // Crop the canonical paired joint around the closed capture ring.
    translate([20,28-H/2,right_print_lift]) intersection() {
        right_pip();
        translate([-20,H/2-28,-right_print_lift]) cube([32,56,60]);
    }
}
module placed_leaf(i) {translate(point(i)) rotate([0,-slope(i),0]) leaf();}
module placed_pin(i) {translate(point(i)) rotate([-90,0,0]) hinge_pin();}
rod_joint_depth=20;
rod_collar_length=3;
rod_collar_r=14;
rod_shaft_bed=7;
assert(male_core_r(thread_offset)-male_bore_d/2>2,
       "Male thread core wall around the axial bore must exceed 2 mm");
assert(rod_shaft_bed-male_bore_d/2>2,
       "Rod shaft flat-bed wall around the axial bore must exceed 2 mm");
rod_socket_bed=female_groove_crest_r(thread_offset)+2;
rod_socket_length=shank-rod_collar_length;
rod_shaft_start=shank-rod_joint_depth-rod_collar_length;
rod_shaft_length=tip_thread+rod_joint_depth+rod_collar_length;
rod_joint_phase=-360*(rod_joint_depth+rod_collar_length)/4;
assert(rod_socket_length>=socket_depth+rod_joint_depth,
       "Rod shank must contain the front socket and rear joint");
assert(rod_shaft_bed<male_core_r(thread_offset), "Rod shaft bed cut must reach the core");
assert(rod_socket_bed-female_groove_crest_r(thread_offset)>=2,
       "Rod socket wall must remain at least 2 mm");
module rod_socket() {
    intersection() {
        difference() {
            cylinder(r=thread_socket_outer_r,h=rod_socket_length,$fn=128);
            translate([0,0,-0.1]) cylinder(r=female_bore_r(),h=rod_socket_length+0.2,$fn=128);
            female_groove(socket_depth,thread_offset);
            translate([0,0,rod_shaft_start]) rotate([0,0,rod_joint_phase])
                female_groove(rod_joint_depth,thread_offset);
        }
        translate([-40,-rod_socket_bed,-1]) cube([80,80,rod_socket_length+2]);
    }
}
module rod_shaft() {
    intersection() {
        difference() {
            union() {
                translate([0,0,rod_shaft_start]) rotate([0,0,rod_joint_phase])
                    male_thread(rod_joint_depth+rod_collar_length,thread_offset);
                translate([0,0,shank]) male_thread(tip_thread,thread_offset);
                translate([0,0,rod_socket_length])
                    cylinder(r=rod_collar_r,h=rod_collar_length,$fn=128);
            }
            // One continuous cut crosses the rear stub, collar and main thread.
            translate([0,0,rod_shaft_start-0.1])
                cylinder(r=male_bore_r,h=rod_shaft_length+0.2,$fn=128);
        }
        translate([-40,-rod_shaft_bed,-1]) cube([80,80,extension_length+2]);
    }
}
module rod_extension() {
    union() {rod_socket();rod_shaft();}
}
module print_rod_socket() {
    translate([thread_socket_outer_r,rod_socket_length,rod_socket_bed]) rotate([90,0,0]) rod_socket();
}
module print_rod_shaft() {
    translate([14,rod_shaft_length,rod_shaft_bed]) rotate([90,0,0])
        translate([0,0,-rod_shaft_start]) rod_shaft();
}
module print_rod_extension() {
    print_rod_socket();
    translate([40,0,0]) print_rod_shaft();
}
module rod_joint_collision() {
    sentinel();
    intersection() {rod_socket();rod_shaft();}
}
module rod_joint_stop_probe() {
    sentinel();
    intersection() {rod_socket();translate([0,0,-0.5]) rod_shaft();}
}
module rod_joint_phase_probe() {
    sentinel();
    intersection() {rod_socket();rotate([0,0,180]) rod_shaft();}
}
module placed_extension(i=0) {
    translate([extension_start(i),H/2,-30]) rotate([0,90,0])
        rotate([0,0,360*extension_turn(i)]) rod_extension();
}
module placed_female() {
    // Rotate the native X-axis rotor around its own axis, then move it inboard
    // to the right support. The source groove remains at local x=-130.
    translate([assembly_span-10,0,0]) translate([0,H/2,-30])
        rotate([360*(final_female_turn-clamp_travel/4)+joint_angle,0,0])
        translate([0,-H/2,30]) female_rotor();
}
module placed_right() {translate([assembly_span-10,0,0]) right_support();}
module placed_left() {translate([10,0,0]) left_support();}
module assembly() {
    for(i=[0:leaf_count-1]) color(i%2?"#82bca3":"#b4d3b7") placed_leaf(i);
    for(i=[0:leaf_count]) color("#e5a25d") placed_pin(i);
    color("#c7de91") placed_left();
    for(i=[0:extension_count-1]) color("#d6c4a8") placed_extension(i);
    color("#7d9cac") placed_female();
    color("#667c70") placed_right();
}
module sentinel() {translate([-30,-30,-60]) cube(1);}
module thread_collision() {
    sentinel();
    intersection() {rod_socket();rod_shaft();}
    for(i=[0:extension_count-1]) {
        intersection() {placed_left(); placed_extension(i);}
        intersection() {placed_extension(i); placed_female();}
    }
    for(i=[0:extension_count-1]) for(j=[0:extension_count-1]) if(j>i)
        intersection() {placed_extension(i); placed_extension(j);}
}
module joint_collision() {
    sentinel();
    for(i=[0:leaf_count-1]) for(j=[0:leaf_count-1]) if(j>i)
        intersection() {placed_leaf(i);placed_leaf(j);}
    for(i=[0:leaf_count]) for(j=[0:leaf_count]) if(j>i)
        intersection() {placed_pin(i);placed_pin(j);}
    for(i=[0:leaf_count]) for(j=[0:leaf_count-1]) intersection() {placed_pin(i);placed_leaf(j);}
    for(i=[0:leaf_count-1]) {
        intersection() {placed_leaf(i);placed_left();}
        intersection() {placed_leaf(i);placed_right();}
    }
    for(i=[0:leaf_count]) {
        intersection() {placed_pin(i);placed_left();}
        intersection() {placed_pin(i);placed_right();}
    }
    for(k=[0:extension_count-1]) for(i=[0:leaf_count-1])
        intersection() {placed_extension(k); placed_leaf(i);}
    for(k=[0:extension_count-1]) for(i=[0:leaf_count])
        intersection() {placed_extension(k); placed_pin(i);}
}
module hardware_collision() {
    sentinel();
    intersection() {placed_female();placed_right();}
    for(i=[0:leaf_count-1]) {
        intersection() {placed_leaf(i);placed_female();}
    }
    for(i=[0:leaf_count]) intersection() {placed_pin(i);placed_female();}
    for(i=[0:extension_count-1]) intersection() {placed_extension(i); placed_right();}
}
module chain_phase_probe() {
    sentinel();
    if(extension_count>1)
        for(i=[0:extension_count-2])
            intersection() {placed_extension(i); translate([2,0,0]) placed_extension(i+1);}
}
// Print selectors reuse the canonical solids and place them on Z=0.
if(part=="print-leaf") print_leaf();
else if(part=="print-fit-kit") fit_kit();
else if(part=="three-leaves") rotate([90,0,0]) three_leaves();
else if(part=="leaf-section") intersection(){leaf();translate([-5,12,-6])cube([55,0.5,12]);}
else if(part=="print-hinge-pin") translate([0,4,1.5]) rotate([0,90,0]) hinge_pin();
else if(part=="print-left-support") translate([10,0,38]) left_support();
else if(part=="print-rod-extension") print_rod_extension();
else if(part=="print-rod-socket") print_rod_socket();
else if(part=="print-rod-shaft") print_rod_shaft();
else if(part=="print-right-pip") translate([140,0,right_print_lift]) right_pip();
else if(part=="print-pip-coupon") pip_coupon();
else if(part=="pip-section") intersection() {pip_coupon();translate([-1,20,-1])cube([42,22,44]);}
else if(part=="print-test-male") translate([10,10,0]) difference() {
    male_thread(32,thread_offset);
    translate([0,0,-0.1]) cylinder(r=male_bore_r,h=32.2,$fn=128);
}
else if(part=="print-test-female") translate([16,16,0]) female_thread(32,thread_offset);
else if(part=="assembly") assembly();
else if(part=="display") rotate([90,0,0]) assembly();
else if(part=="leaf") leaf();
else if(part=="hinge-pin") hinge_pin();
else if(part=="left-support") left_support();
else if(part=="rod-extension") rod_extension();
else if(part=="right-support") right_support();
else if(part=="female") translate([130,-H/2,right_print_lift]) female_rotor();
else if(part=="journal-wall") intersection() {female_thread(); translate([0,0,125]) difference() {cylinder(r=11,h=1,$fn=128);translate([0,0,-0.1])cylinder(r=10,h=1.2,$fn=128);}}
else if(part=="thread-collision") thread_collision();
else if(part=="rod-joint-collision") rod_joint_collision();
else if(part=="rod-joint-stop-probe") rod_joint_stop_probe();
else if(part=="rod-joint-phase-probe") rod_joint_phase_probe();
else if(part=="thread-phase-probe") { sentinel(); intersection() {placed_extension(extension_count-1); translate([2,0,0]) placed_female();} }
else if(part=="chain-phase-probe") chain_phase_probe();
else if(part=="joint-collision") joint_collision();
else if(part=="hardware-collision") hardware_collision();
else if(part=="pip-rotation-check") {sentinel();intersection(){placed_female();placed_right();}}
else if(part=="pip-pull-left") {sentinel();intersection(){translate([-1.2,0,0])placed_female();placed_right();}}
else if(part=="pip-pull-right") {sentinel();intersection(){translate([1.2,0,0])placed_female();placed_right();}}
else assert(false,str("Unknown part: ",part));
