
class InverseLaplaceTransform(object):
    """
    Inverse Laplace transform is implemented using this class
    """

    def __init__(self, ctx):
        self.ctx = ctx

        # a default level of approximation appropriate  
        # for the given precision goal
        self.degree = 18

        # decimal digits of precision for computing p vectors, 
        # and f(t) solutions.  (Talbot and Stehfest have 
        # their own expressions that override this minimum)
        self.dps_goal = 30
        
        self.debug = 0

    def calc_laplace_parameter(self,t,**kwargs):
        raise NotImplementedError

    def calc_time_domain_solution(self,fp):
        raise NotImplementedError

class FixedTalbot(InverseLaplaceTransform):
    
    def calc_laplace_parameter(self, t, **kwargs):

        # time of desired approximation
        self.t = self.ctx.convert(t)

        # maximum time desired (used for scaling)
        self.tmax = self.ctx.convert(kwargs.get('tmax',self.t))

        # integer order of approximation
        self.degree = kwargs.get('degree',self.degree)

        # rule for extended precision from Abate & Valko (2004)
        # "Multi-precision Laplace Transform Inversion"
        self.dps_goal = kwargs.get('dps',max(self.dps_goal,self.degree))

        # Abate & Valko rule of thumb
        self.r = kwargs.get('r',2*self.degree/(5*self.tmax))
        
        self.debug = kwargs.get('debug',self.debug)

        M = self.degree
        self.p = self.ctx.matrix(M,1)
        self.p[0] = self.r

        with self.ctx.workdps(self.dps_goal):
            self.theta = self.ctx.linspace(0.0, self.ctx.pi, M+1)

            for i in range(1,M):
                self.p[i] = self.r*self.theta[i]*( 
                    self.ctx.cot(self.theta[i]) + 1j)
    
        if self.debug > 1:
            print 'FixedTalbot p:',self.p
        if self.debug > 2:
            print ('FixedTalbot tmax,degree,dps_goal,r',
                   self.tmax,self.degree,self.dps_goal,self.r)

    def calc_time_domain_solution(self,fp):

        theta = self.theta
        M = self.degree
        t = self.t
        p = self.p
        r = self.r
        ans = self.ctx.matrix(M,1)

        with self.ctx.workdps(self.dps_goal):

            for i in range(1,M):
                ans[i] = self.ctx.exp(t*p[i])*fp[i]*(
                    1 + (theta[i] + (theta[i]*self.ctx.cot(theta[i]) - 1)
                         *self.ctx.cot(theta[i]))*1j)
    
            result = r/M*(fp[0]/2*self.ctx.exp(r*t) + self.ctx.fsum(ans))

        return result.real

# ****************************************

class Weeks(InverseLaplaceTransform):
    
    def calc_laplace_parameter(self, t, **kwargs):

        # time of desired approximation
        self.t = self.ctx.convert(t)

        # maximum time desired (used for scaling)
        self.tmax = self.ctx.convert(kwargs.get('tmax',self.t))

        # equations defined in terms of 2M below;
        # number of quadrature points
        self.degree = int(kwargs.get('degree',self.degree)/2.0)

        # highest Laguerre polynomial degree
        self.N = kwargs.get('N',self.degree)

        # F(p) ~ p**(-s), as p -> infinity (also as t -> 0)
        self.s = self.ctx.convert(kwargs.get('s',1))    

        # Weeks' rules of thumb (can improve on these?)
        self.kappa = self.ctx.convert(kwargs.get('kappa',1/self.tmax))
        self.b = self.ctx.convert(kwargs.get('b',self.N*self.kappa))

        # no real rule of thumb for increasing precsion as 
        # degree of approximation increases
        self.dps_goal = kwargs.get('dps',self.dps_goal)

        self.debug = kwargs.get('debug',self.debug)

        M = self.degree
        self.z = self.ctx.matrix(2*M,1)
        self.p = self.ctx.matrix(2*M,1)
        self.theta = self.ctx.matrix(2*M,1)

        with self.ctx.workdps(self.dps_goal):

            for i in range(2*M):
                self.theta[i] = ((i-M)+0.5)/M
                # midpoint rule around unit circle
                self.z[i] = self.ctx.expjpi(self.theta[i]) # fcn includes i*pi
    
            for j in range(2*M):
                # Mobius mapping back onto right half plane
                self.p[j] = self.kappa - self.b/2 + self.b/(1-self.z[j])

        if self.debug > 1:
            print 'Weeks p:',self.p
        if self.debug > 2:
            print ('Weeks tmax,degree,N,s,kappa,b,dps_goal:',
            self.tmax,self.degree,self.N,self.s,
            self.kappa,self.b,self.dps_goal)

    def _coeff(self,n,fp):
        """use midpoint rule for calculating a_n coefficients
        this is the approach of Weideman (1999)."""

        M = self.degree
        b = self.b
        s = self.s
        z = self.z
        theta = self.theta
        arg = self.ctx.matrix(2*M,1)

        for i in range(2*M):
            # fcn includes i*pi
            arg[i] = (self.ctx.power(b/(1-z[i]),s)*
                      fp[i]*self.ctx.expjpi(-theta[i]*n))

        return self.ctx.fsum(arg)/(2*M)

    def calc_time_domain_solution(self,fp):

        b = self.b
        s = self.s
        kappa = self.kappa
        N = self.N
        t = self.t
        arg = self.ctx.matrix(N,1)

        with self.ctx.workdps(self.dps_goal):

            for n in range(N):
                arg[n] = (self._coeff(n,fp)*self.ctx.fac(n)/
                          self.ctx.fac(s+n-1)*self.ctx.laguerre(n,s-1,b*t))
    
            result = (self.ctx.exp(t*(kappa - b/2))*
                      self.ctx.power(t,s-1)*self.ctx.fsum(arg))

        return result.real

# ****************************************

class Piessens(InverseLaplaceTransform):

    def calc_laplace_parameter(self, t, **kwargs):

        # time of desired approximation
        self.t = self.ctx.convert(t)
        
        # maximum time desired (used for scaling)
        self.tmax = self.ctx.convert(kwargs.get('tmax',self.t))

        # M+1 terms are used below
        self.degree = kwargs.get('degree',self.degree)

        # highest 2F2 degree
        self.N = kwargs.get('N',self.degree)

        # F(p) ~ p**(-s), as p -> infinity (and as t -> 0)
        self.s = self.ctx.convert(kwargs.get('s',1))

        # Piessens didn't have a good "rule of thumb"?
        self.b = self.ctx.convert(kwargs.get('b',1/(self.N*self.tmax)))

        # no real rule of thumb for increasing precsion as 
        # degree of approximation increases
        self.dps_goal = kwargs.get('dps',self.dps_goal)

        self.debug = kwargs.get('debug',self.debug)

        M = self.degree
        self.theta = self.ctx.matrix(M+1,1)
        self.z = self.ctx.matrix(M+1,1)
        self.p = self.ctx.matrix(M+1,1)
        
        with self.ctx.workdps(self.dps_goal):

            for i in range(M+1):
                self.theta[i] = self.ctx.fraction(2*i+1,(M+1)*2)
                # pi included in fcn
                self.z[i] = self.ctx.cospi(self.theta[i]) 
    
            for j in range(M+1):
                self.p[j] = self.b/(1-self.z[j])

        if self.debug > 1:
            print 'Piessens p:',self.p
        if self.debug > 2:
            print ('Piessens tmax,degree,N,s,b,dps_goal:',
                   self.tmax,self.degree,self.N,self.s,self.b,self.dps_goal)

    def _coeff(self,n,fp):
        """use quadrature rule for calculating coefficients."""

        M = self.degree
        s = self.s
        b = self.b
        z = self.z
        theta = self.theta
        arg = self.ctx.matrix(M+1,1)

        for i in range(M+1):
            # pi included in fcn
            arg[i] = (self.ctx.power(b/(1-z[i]),s)*
                      fp[i]*self.ctx.cospi(theta[i]*n))

        return self.ctx.fraction(2,M+1)*self.ctx.fsum(arg)

    def calc_time_domain_solution(self,fp):

        s = self.s
        b = self.b
        N = self.N
        t = self.t
        arg = self.ctx.matrix(N,1)

        with self.ctx.workdps(self.dps_goal):

            for n in range(N):
                arg[n] = (self._coeff(n,fp)*
                          self.ctx.hyp2f2(-n,n,0.5,s,b*t))
    
            arg[0] /= 2.0
            result = (self.ctx.power(t,s-1)/self.ctx.gamma(s)*
                      self.ctx.fsum(arg))

        # ignore any small imaginary part
        return result.real

# ****************************************

class Stehfest(InverseLaplaceTransform):

    def calc_laplace_parameter(self, t, **kwargs):

        # time of desired approximation
        self.t = self.ctx.convert(t)

        self.degree = kwargs.get('degree',self.degree)

        # rule for extended precision from Abate & Valko (2004)
        # "Multi-precision Laplace Transform Inversion"
        self.dps_goal = kwargs.get('dps',max(self.dps_goal,
                                               2.1*self.degree))

        self.debug = kwargs.get('debug',self.debug)

        M = self.degree

        # don't compute V here, too expensive (?)
        self.V = kwargs.get('V',None)       

        with self.ctx.workdps(self.dps_goal):

            self.p = (self.ctx.matrix(self.ctx.arange(1,M+1))*
                      self.ctx.ln2/self.t)
    
        if self.debug > 1:
            print 'Stehfest p:',self.p
        if self.debug > 2:
            print ('Stehfest degree,dps_goal:',
            self.tmax,self.degree,self.dps_goal)


    def _coeff(self):
        """Stehfest coefficients only depend on M"""

        M = self.degree
        # order must be odd
        assert M%2 == 0
        M2 = M/2

        self.V = self.ctx.matrix(M,1)

        # Salzer summation weights
        for k in range(1,M+1):
            z = self.ctx.matrix(int(min(k,M2)+1),1)
            for j in range(int(self.ctx.floor((k+1)/2.0)),min(k,M2)+1):
                z[j] = (j**M2*self.ctx.fac(2*j)/
                        (self.ctx.fac(M2-j)*self.ctx.fac(j)*
                         self.ctx.fac(j-1)*
                         self.ctx.fac(k-j)*self.ctx.fac(2*j-k)))
            self.V[k-1] = self.ctx.power(-1,k+M2)*self.ctx.fsum(z)

    def calc_time_domain_solution(self,fp):
        """Compute time-domain solution using f(p)
        and coefficients"""

        with self.ctx.workdps(self.dps_goal):

            if self.V is None:
                self._coeff()
            else:
                self.V = self.ctx.convert(self.V)
    
            result = self.ctx.fdot(self.V,fp)*self.ctx.ln2/self.t

        # ignore any small imaginary part
        return result.real

# ****************************************

class GaverRho(InverseLaplaceTransform):

    def calc_laplace_parameter(self, t, **kwargs):

        # time of desired approximation
        self.t = self.ctx.convert(t)

        self.degree = kwargs.get('degree',self.degree)

        # rule for extended precision from Abate & Valko (2004)
        # "Multi-precision Laplace Transform Inversion"
        self.dps_goal = kwargs.get('dps',max(self.dps_goal,
                                               2.1*self.degree))

        self.debug = kwargs.get('debug',self.debug)

        M = self.degree
        if M%2 == 1:
            M += 1
            self.degree = M

        with self.ctx.workdps(self.dps_goal):
            self.tau = self.ctx.ln2/self.t
            
            self.p = (self.ctx.matrix(self.ctx.arange(1,M+1))*self.tau)
    
        if self.debug > 1:
            print 'Stehfest p:',self.p
        if self.debug > 2:
            print ('Stehfest degree,dps_goal:',
            self.tmax,self.degree,self.dps_goal)

    def calc_time_domain_solution(self,fp):
        """Compute time-domain solution using f(p)
        and coefficients"""

        M = self.degree
        M2 = M/2

        with self.ctx.workdps(self.dps_goal):
       
            # compute Gaver functionals 
            fkt = self.ctx.matrix(M2,1)
            arg = self.ctx.matrix(M2+1,1)
       
            for k in range(1,M2+1):
                arg[:] = 0.0 
                for j in range(k+1):
                    print M,M2,k,j,fp.rows
                    arg[j] = (self.ctx.power(-1,j)*
                              self.ctx.binomial(k,j)*fp[j+k-1])
       
                fkt[k-1] = (k*self.tau*self.ctx.binomial(2*k,k)*
                            self.ctx.fsum(arg[0:k+1]))
           
            # apply Wynn's Rho non-linear 
            # sequence transformation 
            rho = self.ctx.matrix(M2,M2+2)
           
            # rho[:,0] = 0.0
            rho[:,1] = fkt
           
            print M,M2,rho.rows,rho.cols

            for k in range(2,M2+2):
                for n in range(M2-(k-2)*2 - 1):
                    denom = rho[n+1,k-1] - rho[n,k-1]
                    print k,n,M2-(k-2)*2 - 1,denom
                    print rho
                    if abs(denom) > self.ctx.eps:
                        rho[n,k] = rho[n+1,k-2] + k/denom
                    else:
                        print "Wynn's Rho cancellation at ",k,n
                        return rho[n-1,k-1+2]

        # ignore any small imaginary part
        return rho[0,M2+2].real

# ****************************************

class deHoog(InverseLaplaceTransform):

    def calc_laplace_parameter(self, t, **kwargs):

        self.t = self.ctx.convert(t)

        # 2*M+1 terms are used below
        self.degree = int(kwargs.get('degree',self.degree)/2.0)

        # abcissa of convergence (rightmost pole)
        self.alpha = self.ctx.convert(kwargs.get('alpha',1.0E-8))

        # desired tolerance
        self.tol =   self.ctx.convert(kwargs.get('tol',1.0E-7))
        self.np = 2*self.degree+1

        # scaling factor
        self.T = self.ctx.convert(kwargs.get('T',2*self.t))        

        # no real rule of thumb for increasing precsion as 
        # degree of approximation increases
        self.dps_goal = kwargs.get('dps',self.dps_goal)

        self.debug = kwargs.get('debug',self.debug)

        M = self.degree
        T = self.T
        self.p = self.ctx.matrix(2*M+1,1)

        with self.ctx.workdps(self.dps_goal):

            for i in range(2*M+1):
                self.p[i] = (self.alpha - 
                             self.ctx.log(self.tol)/(2*T) + 
                             self.ctx.pi*i/T*1j)

        if self.debug > 1:
            print 'de Hoog p:',self.p
        if self.debug > 2:
            print ('de Hoog degree,alpha,tol,T,dps_goal:',
                   self.degree,self.alpha,self.tol,self.T,self.dps_goal)

    def calc_time_domain_solution(self,fp):

        M = self.degree
        np = self.np
        t = self.t
        T = self.T
        alpha = self.alpha
        tol = self.tol

        gamma = alpha - self.ctx.log(tol)/(2*T)

        e = self.ctx.matrix(np,M+1)
        q = self.ctx.matrix(np,M)
        d = self.ctx.matrix(np,1)
        A = self.ctx.matrix(np+2,1)
        B = self.ctx.matrix(np+2,1)

        self.dps_orig = self.ctx.dps
        self.ctx.dps = self.dps_goal

        # initialize Q-D table
        e[0:2*M,0] = 0.0
        q[0,0] = fp[1]/(fp[0]/2)
        for i in range(1,2*M):
            q[i,0] = fp[i+1]/fp[i]

        # rhombus rule for filling triangular Q-D table
        for r in range(1,M+1):
            # start with e, column 1, 0:2*M-2
            mr = 2*(M-r)
            e[0:mr,r] = q[1:mr+1,r-1] - q[0:mr,r-1] + e[1:mr+1,r-1]
            if not r == M:
                rq = r+1
                mr = 2*(M-rq)+1
                for i in range(mr):
                    q[i,rq-1] = q[i+1,rq-2]*e[i+1,rq-1]/e[i,rq-1]

        # build up continued fraction coefficients
        d[0] = fp[0]/2
        for r in range(1,M+1):
            d[2*r-1] = -q[0,r-1] # even terms
            d[2*r]   = -e[0,r]   # odd terms

        # seed A and B for recurrence
        A[0] = 0.0
        A[1] = d[0]
        B[0:2] = 1.0

        # base of the power series
        z = self.ctx.expjpi(t/T) # i*pi is already in fcn

        # coefficients of Pade approximation
        # using recurrence for all but last term
        for i in range(1,2*M):
            A[i+1] = A[i] + d[i]*A[i-1]*z
            B[i+1] = B[i] + d[i]*B[i-1]*z

        # "improved remainder" to continued fraction
        brem  = (1 + (d[2*M-1] - d[2*M])*z)/2
        # powm1(x,y) computes x^y - 1 more accurately near zero
        rem = brem*self.ctx.powm1(1 + d[2*M]*z/brem,0.5)

        # last term of recurrence using new remainder
        A[np] = A[2*M] + rem*A[2*M-1]
        B[np] = B[2*M] + rem*B[2*M-1]

        # diagonal Pade approximation
        # F=A/B represents accelerated trapezoid rule
        result = self.ctx.exp(gamma*t)/T*(A[np]/B[np]).real

        self.ctx.dps = self.dps_orig
        return result

# ****************************************

class LaplaceTransformInversionMethods:
    def __init__(ctx, *args, **kwargs):
        ctx._fixed_talbot = FixedTalbot(ctx)
        ctx._weeks = Weeks(ctx)
        ctx._piessens = Piessens(ctx)
        ctx._stehfest = Stehfest(ctx)
        ctx._gaverrho = GaverRho(ctx)
        ctx._de_hoog = deHoog(ctx)

    def invertlaplace(ctx, f, t, **kwargs):
        r"""
        Computes the numerical inverse Laplace transform for a 
        Laplace-space function at a given time.  The function being
        estimated is assumed to be a real-only function of time.
        """
        
        rule = kwargs.get('method','stehfest')
        if type(rule) is str:
            lrule = rule.lower()
            if lrule == 'talbot' or lrule == 'fixed-talbot':
                rule = ctx._fixed_talbot
            elif lrule == 'weeks':
                rule = ctx._weeks
            elif lrule == 'piessens':
                rule = ctx._piessens
            elif lrule == 'stehfest':
                rule = ctx._stehfest
            elif lrule == 'gaverrho':
                rule = ctx._gaverrho
            elif lrule == 'dehoog' or lrule == 'de-hoog':
                rule = ctx._de_hoog
            else:
                raise ValueError("unknown inversion method: %s" % rule)
        else:
            rule = rule(ctx)
    
        rule.calc_laplace_parameter(t,**kwargs)
        np = rule.p.rows # p is a column vector
        fp = ctx.matrix(np,1)
        for i in range(np):
            fp[i] = f(rule.p[i])
        v = rule.calc_time_domain_solution(fp)
        return v

    def invlaptalbot(ctx, *args, **kwargs):
        kwargs['method'] = 'talbot'
        return ctx.invertlaplace(*args, **kwargs)

    def invlapweeks(ctx, *args, **kwargs):
        kwargs['method'] = 'weeks'
        return ctx.invertlaplace(*args, **kwargs)

    def invlappiessens(ctx, *args, **kwargs):
        kwargs['method'] = 'piessens'
        return ctx.invertlaplace(*args, **kwargs)
    
    def invlapstehfest(ctx, *args, **kwargs):
        kwargs['method'] = 'stehfest'
        return ctx.invertlaplace(*args, **kwargs)

    def invlapgaverrho(ctx, *args, **kwargs):
        kwargs['method'] = 'gaverrho'
        return ctx.invertlaplace(*args, **kwargs)

    def invlapdehoog(ctx, *args, **kwargs):
        kwargs['method'] = 'dehoog'
        return ctx.invertlaplace(*args, **kwargs)

# ****************************************

#if __name__ == '__main__':
    #import doctest
    #doctest.testmod()
