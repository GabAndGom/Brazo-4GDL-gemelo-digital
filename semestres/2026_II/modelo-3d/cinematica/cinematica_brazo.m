% Cinemática del brazo XK-JS1-1 (4 GDL) en MATLAB / Octave.
%
% Lee parametros.json (generado por pruebas_cinematica.js desde
% web/js/cinematica.js), calcula la cinemática directa e inversa, el jacobiano
% y dibuja el espacio de trabajo. Equivale a graficas_cinematica.py.
% Requiere MATLAB R2016b o superior (jsondecode) u Octave 7+.
%
% No se pudo ejecutar al escribirlo (no hay MATLAB en la PC de desarrollo);
% las mismas ecuaciones están probadas en JavaScript y Python.

clear; clc;
dir_script = fileparts(mfilename('fullpath'));
datos = jsondecode(fileread(fullfile(dir_script, 'parametros.json')));
P = datos.parametros;  D = datos.derivados;

% ---------------------------------------------------------------- directa
fk = @(theta, sX, sY) directa(P, D, theta, sX, sY);

q = [30, 80, 60];                       % [theta_deg, sX_mm, sY_mm]
k = fk(q(1), q(2), q(3));
fprintf('Directa: theta=%g, sX=%g, sY=%g -> X=%.1f Y=%.1f Z=%.1f mm (phi=%.1f deg)\n', ...
        q, k.X, k.Y, k.Z, k.phi);

% ---------------------------------------------------------------- inversa
qi = inversa(P, D, k.X, k.Y, k.Z);
fprintf('Inversa: theta=%.4f sX=%.4f sY=%.4f\n', qi);

% ---------------------------------------------------------------- jacobiano numérico
h = 1e-4; J = zeros(3);
for c = 1:3
    dq = zeros(1,3); dq(c) = h;
    a = fk(q(1)+dq(1), q(2)+dq(2), q(3)+dq(3));
    b = fk(q(1)-dq(1), q(2)-dq(2), q(3)-dq(3));
    J(:,c) = ([a.X; a.Y; a.Z] - [b.X; b.Y; b.Z]) / (2*h);
end
J(:,1) = J(:,1) * 180/pi;               % derivada respecto a theta en rad
disp('Jacobiano d(X,Y,Z)/d(theta[rad], sX, sY):'); disp(J);
fprintf('det(J) = %.1f\n', det(J));

% ---------------------------------------------------------------- relación motor -> articulación
T = datos.transmision;
fprintf('X, Y: %.6f mm/pulso (%g pulsos/mm)\n', T.mmPorPulso, T.pulsosPorMm);
fprintf('Base: %.4f deg/pulso (%g pulsos/deg)\n', T.gradosPorPulso, T.pulsosPorGrado);

% ---------------------------------------------------------------- espacio de trabajo
[SX, SY] = meshgrid(linspace(0, P.recorridoX, 41), linspace(0, P.recorridoY, 41));
R = zeros(size(SX)); Z = R;
for i = 1:numel(SX)
    k = fk(0, SX(i), SY(i)); R(i) = k.r; Z(i) = k.z;
end
figure('Name', 'Espacio de trabajo');
subplot(1,2,1); plot(R(:), Z(:), '.', 'Color', [0.76 0.38 0.05]); axis equal; grid on;
xlabel('r [mm]'); ylabel('z [mm]'); title('Corte r-z');
subplot(1,2,2);
t = linspace(P.thetaMin, P.thetaMax, 200) * pi/180;
fill([max(R(:))*cos(t), min(R(:))*cos(fliplr(t))], [max(R(:))*sin(t), min(R(:))*sin(fliplr(t))], ...
     [0.95 0.75 0.55]); axis equal; grid on;
xlabel('X [mm]'); ylabel('Y [mm]'); title('Vista superior');

% ================================================================ funciones
function psi = psi_de(P, D, g)
    cx = g + D.cu0; cz = D.ch;
    dist = hypot(cx, cz);
    cosg = (P.a^2 + dist^2 - P.L12^2) / (2*P.a*dist);
    psi = atan2(cz, cx) - acos(cosg);
end

function k = directa(P, D, theta, sX, sY)
    % sY = 0 en el final inferior (homing); g = posición del bloque 1 desde su tope trasero
    psi = psi_de(P, D, P.recorridoY - sY);
    phi = psi - P.beta*pi/180;
    uA = D.u5_0 + sX + P.uA;
    Eu = uA + P.L9*cos(phi);  Eh = D.hA + P.L9*sin(phi);
    k.phi = phi*180/pi;
    k.r = Eu + P.dg;  k.z = Eh - P.hg;
    k.X = k.r*cosd(theta);  k.Y = k.r*sind(theta);  k.Z = k.z;
end

function q = inversa(P, D, X, Y, Z)
    % Rama "adelante" del brazo y rama de montaje real de la biela 12
    r = hypot(X, Y);  theta = atan2d(Y, X);
    s = (Z + P.hg - D.hA) / P.L9;
    if abs(s) > 1, error('Altura inalcanzable'); end
    phi = asin(s);
    sX = r - P.dg - P.L9*cos(phi) - D.u5_0 - P.uA;
    psi = phi + P.beta*pi/180;
    bx = P.a*cos(psi);  bz = P.a*sin(psi);
    g = bx - sqrt(P.L12^2 - (D.ch - bz)^2) - D.cu0;
    if abs(psi_de(P, D, g) - psi) > 1e-6         % probar la otra raíz
        g = bx + sqrt(P.L12^2 - (D.ch - bz)^2) - D.cu0;
    end
    sY = P.recorridoY - g;
    q = [theta, sX, sY];
    if sX < 0 || sX > P.recorridoX || sY < 0 || sY > P.recorridoY
        warning('Fuera de recorrido');
    end
end
