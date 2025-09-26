


f = @(x,y,z,lbd) [1-lbd/x^2;2*y-2*lbd/y^2;3*z^2-3*lbd/z^2;1/x+2/y+3/z-1];
df = @(x,y,z,lbd) [[2*lbd/x^3,0,0,-1/x^2];[0,2+4*lbd/y^3,0,-2/y^2];[0,0,6*z+6*lbd/z^3,-3/z^2];[-1/x^2,-2/y^2,-3/z^2,0]];


x0=[1,1,1,1];
tol = 1e-3;
max_iter = 20;
err=f(x0(1),x0(2),x0(3),x0(4));

x_i = x0;

for ii=1:max_iter
    if all(err<tol)
        disp 'stopped'
        break;
    end
    x_i = x_i - f(x_i(1),x_i(2),x_i(3),x_i(4))'*inv(df(x_i(1),x_i(2),x_i(3),x_i(4)));
    err = f(x_i(1),x_i(2),x_i(3),x_i(4));
    fprintf('iteration: %d\n',ii);
end

fprintf('optimal solution:\n');
fprintf('x=%.2f\n',x_i(1));
fprintf('y=%.2f\n',x_i(2));
fprintf('z=%.2f\n',x_i(3));
fprintf('lbd=%.2f\n',x_i(4));
%f(x_i(1),x_i(2),x_i(3),x_i(4))

fprintf('cost function at optimum: %.3f\n',x_i(1)+x_i(2)^2+x_i(3)^3);
fprintf('equality constraint: %.3f\n',1/x_i(1)+2/x_i(2)+3/x_i(3))