// ISO Metric Trapezoidal Thread TR20x4 (7e/7H), RH. Local axis +Z.
part = "male";
W = 200;
// Signed offset applied to both mating thread profiles. Negative shrinks the
// male root and opens the female groove/bearing clearance.
thread_offset = -0.25;
$fn = 128;

thread_pitch = 4;
thread_included_angle = 30;
thread_flank_angle = thread_included_angle / 2;
thread_root_overlap = 0.15;

// Installed Fusion ThreadData values for ISO Metric Trapezoidal Threads,
// TR20x4, external 7e / internal 7H. Radii are kept here in mm so the SCAD
// source and the native Thread feature use the same contract.
male_minor_r = 15.287 / 2;
male_pitch_r = 17.7725 / 2;
male_major_r = 19.85 / 2;
female_minor_r = 16.1875 / 2;
female_pitch_r = 18.1775 / 2;
female_major_r = 20.5 / 2;
female_od_r = 14;
male_length = 130;
female_length = 130;
samples_per_turn = 32;

assert(thread_offset <= -0.1 && thread_offset >= -0.4,
       "thread_offset must be -0.4..-0.1 mm (retain printable TR20x4 crests)");

function profile_r(p, j) = p[j][0];
function profile_z(p, j) = p[j][1];
function male_core_r(offset=thread_offset) = male_minor_r + offset;
function male_profile_root_r(offset=thread_offset) = male_core_r(offset) - thread_root_overlap;
function female_bore_r() = female_minor_r;
function female_profile_root_r() = female_bore_r() - thread_root_overlap;
function male_crest_halfwidth(r, offset=thread_offset) =
    thread_pitch/4 - (r - male_pitch_r)*tan(thread_flank_angle)
    + offset/cos(thread_flank_angle);
function female_crest_halfwidth(r, offset=thread_offset) =
    thread_pitch/4 - (r - female_pitch_r)*tan(thread_flank_angle)
    - offset/cos(thread_flank_angle);
function male_profile(offset=thread_offset) = let(
    root_r = male_profile_root_r(offset), crest_r = male_major_r,
    root_w = male_crest_halfwidth(root_r, offset),
    crest_w = male_crest_halfwidth(crest_r, offset)
) [[root_r,-root_w],[crest_r,-crest_w],[crest_r,crest_w],[root_r,root_w]];
function female_groove_crest_r(offset=thread_offset) = female_major_r - offset;
function female_profile(offset=thread_offset) = let(
    root_r = female_profile_root_r(), crest_r = female_groove_crest_r(offset),
    root_w = female_crest_halfwidth(root_r, offset),
    crest_w = female_crest_halfwidth(crest_r, offset)
) [[root_r,-root_w],[crest_r,-crest_w],[crest_r,crest_w],[root_r,root_w]];

// A radial/axial trapezoid follows a true helix around Z. Extending one turn
// past either end lets the finishing box produce clean, capped thread starts.
module helical_sweep(length, profile) {
    turns = length/thread_pitch + 2;
    steps = ceil(turns*samples_per_turn);
    z0 = -thread_pitch;
    dz = (length + 2*thread_pitch)/steps;
    points = [for (i=[0:steps], j=[0:3]) let(
        zc = z0 + i*dz,
        // Fusion's standard TR20x4 probe places the theta=0 crest center at
        // z=3P/4 modulo P. The common phase keeps male and female anchored.
        a = 360*(zc - 3*thread_pitch/4)/thread_pitch,
        r = profile_r(profile,j),
        z = zc + profile_z(profile,j)
    ) [r*cos(a), r*sin(a), z]];
    side_faces = [for (i=[0:steps-1], j=[0:3]) let(
        a=i*4+j, b=i*4+(j+1)%4,
        c=(i+1)*4+(j+1)%4, d=(i+1)*4+j
    ) [a,b,c,d]];
    end_faces = [[3,2,1,0], [steps*4,steps*4+1,steps*4+2,steps*4+3]];
    intersection() {
        polyhedron(points=points, faces=concat(side_faces,end_faces), convexity=10);
        translate([-11,-11,0]) cube([22,22,length]);
    }
}

module male_thread(length=130, offset=thread_offset) {
    // The profile root overlaps the offset TR20x4 minor core by 0.15 mm.
    union() {
        cylinder(h=length, r=male_core_r(offset), $fn=128);
        helical_sweep(length, male_profile(offset));
    }
}

module female_groove(length=130, offset=thread_offset) {
    union() {
        // The profile root overlaps the standard internal minor bore by 0.15 mm.
        cylinder(h=length+0.2, r=female_bore_r(), $fn=128);
        helical_sweep(length+0.2, female_profile(offset));
    }
}

module female_thread(length=130, offset=thread_offset) {
    difference() {
        union() {
            cylinder(h=length-10, r=female_od_r, $fn=128);
            translate([0,0,length-10]) cylinder(h=2,r1=14,r2=12,$fn=128);
            translate([0,0,length-8]) cylinder(h=8,r=12,$fn=128);
            // Captive double cone: each ramp is 45 degrees in print orientation.
            translate([0,0,length]) cylinder(h=4,r1=12,r2=16,$fn=128);
            translate([0,0,length+4]) cylinder(h=4,r1=16,r2=12,$fn=128);
            // This end and the stationary plate both start on the print bed.
            translate([0,0,length+8]) cylinder(h=2,r=12,$fn=128);
        }
        // Thread stops before journal; the standard minor bore continues through
        // the smooth journal and leaves the existing wall arrangement intact.
        female_groove(length-12, offset);
        translate([0,0,-0.1]) cylinder(h=length+10.2,r=female_bore_r(),$fn=128);
    }
}

if (part == "male") male_thread(male_length);
if (part == "female") female_thread(female_length, thread_offset);
if (part == "fdm-profile-check") {
    // A standard 30 degree included angle is intentional. This gate checks
    // profile identity and positive FDM clearance; it does not classify the
    // 15 degree flanks as a 45 degree source-overhang limit.
    assert(abs(thread_included_angle - 30) < 0.0001,
        "TR20x4 must keep the 30 degree included flank angle");
    assert(female_groove_crest_r() > male_major_r,
        "FDM crest clearance must remain positive");
    assert(female_bore_r() > male_core_r(),
        "FDM root clearance must remain positive");
    cube(1);
}
if (part == "offset-check") {
    assert(abs(male_core_r() - 7.3935) < 0.0001,
        "TR20x4 male offset core radius must be 7.3935 mm");
    assert(abs(male_profile()[0][0] - 7.2435) < 0.0001,
        "Male profile root must overlap the offset core by 0.15 mm");
    assert(abs(male_profile()[1][0] - 9.925) < 0.0001,
        "TR20x4 male crest radius must remain 9.925 mm");
    assert(abs(female_bore_r() - 8.09375) < 0.0001,
        "TR20x4 female minor bore radius must remain 8.09375 mm");
    assert(abs(female_profile()[0][0] - 7.94375) < 0.0001,
        "Female profile root must overlap the bore by 0.15 mm");
    assert(abs(female_profile()[1][0] - 10.5) < 0.0001,
        "TR20x4 female groove crest radius must be 10.5 mm");
    cube(1);
}
// W=200 nominal engagement test: the female origin is translated by 50 mm,
// so its helix is phase-shifted half a turn to mate with the male.
if (part == "pair-test") {
    assert(W >= 180 && W <= 250, "W must be 180..250 mm");
    translate([0,0,10]) male_thread(male_length);
    translate([0,0,W-140]) rotate([0,0,360*(W-150)/thread_pitch])
        female_thread(female_length, thread_offset);
}
