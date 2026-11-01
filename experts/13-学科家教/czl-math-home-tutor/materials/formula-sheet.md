# 公式速查（讲题时按名称引用，不整页背）

> 数学公式本身属于公有领域的客观事实，本文件的**选编、条件标注与易错提示**为原创整理。
> 使用纪律：引用公式时必须同时说清**适用条件**。只报公式不说条件，是 C 码（概念）的主要来源。

## 一、代数与不等式

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 基本不等式 | $a+b\ge 2\sqrt{ab}$ | $a,b>0$；取等当且仅当 $a=b$ |
| 变形 | $ab\le\left(\frac{a+b}{2}\right)^2$ | 同上 |
| 一元二次求根 | $x=\dfrac{-b\pm\sqrt{b^2-4ac}}{2a}$ | 先看 $\Delta$ 符号 |
| 韦达定理 | $x_1+x_2=-\dfrac ba,\ x_1x_2=\dfrac ca$ | 必须 $\Delta\ge0$ 才能用 |
| 绝对值不等式 | $\big||a|-|b|\big|\le|a+b|\le|a|+|b|$ | 取等条件方向相反，别记反 |

## 二、函数与导数

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 幂函数 | $(x^n)'=nx^{n-1}$ | $n$ 为任意实数，定义域内 |
| 指数 | $(e^x)'=e^x$，$(a^x)'=a^x\ln a$ | $a>0,a\ne1$ |
| 对数 | $(\ln x)'=\dfrac1x$，$(\log_a x)'=\dfrac{1}{x\ln a}$ | $x>0$ |
| 三角 | $(\sin x)'=\cos x$，$(\cos x)'=-\sin x$ | 别丢负号 |
| 乘积法则 | $(uv)'=u'v+uv'$ | |
| 商法则 | $\left(\dfrac uv\right)'=\dfrac{u'v-uv'}{v^2}$ | $v\ne0$ |
| 复合函数 | $\big(f(g(x))\big)'=f'(g(x))\cdot g'(x)$ | 漏乘内层导数是高频错 |
| 切线 | $y-f(x_0)=f'(x_0)(x-x_0)$ | 在点 vs 过点，两回事 |
| 常用放缩 | $e^x\ge x+1$；$\ln x\le x-1$；$\ln x\ge 1-\dfrac1x$ | 均在 $x>0$，等号在 $x=1$ |

## 三、三角函数与解三角形

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 和差角 | $\sin(A\pm B)=\sin A\cos B\pm\cos A\sin B$ | 符号跟着 $\sin$ 走 |
| 和差角 | $\cos(A\pm B)=\cos A\cos B\mp\sin A\sin B$ | 符号与 $\sin$ 相反 |
| 二倍角 | $\sin2A=2\sin A\cos A$；$\cos2A=\cos^2A-\sin^2A$ | 三种形式按需选 |
| 降幂 | $\sin^2A=\dfrac{1-\cos2A}{2}$，$\cos^2A=\dfrac{1+\cos2A}{2}$ | 求周期必用 |
| 辅助角 | $a\sin x+b\cos x=\sqrt{a^2+b^2}\sin(x+\varphi)$ | $\tan\varphi=\dfrac ba$，象限由 $(a,b)$ 定 |
| 正弦定理 | $\dfrac{a}{\sin A}=\dfrac{b}{\sin B}=\dfrac{c}{\sin C}=2R$ | 已知两边一对角时可能两解 |
| 余弦定理 | $a^2=b^2+c^2-2bc\cos A$ | 求角用变形 $\cos A=\dfrac{b^2+c^2-a^2}{2bc}$ |
| 面积 | $S=\dfrac12ab\sin C=\dfrac12ah$ | 也可 $S=\dfrac{abc}{4R}$ |
| 射影 | $a=b\cos C+c\cos B$ | 化简边角关系时好用 |

## 四、数列

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 等差通项 | $a_n=a_1+(n-1)d$ | |
| 等差求和 | $S_n=\dfrac{n(a_1+a_n)}{2}=na_1+\dfrac{n(n-1)}{2}d$ | |
| 等比通项 | $a_n=a_1q^{n-1}$ | $q\ne0$ |
| 等比求和 | $S_n=\dfrac{a_1(1-q^n)}{1-q}$ | $q\ne1$；$q=1$ 时 $S_n=na_1$ |
| 前 $n$ 项与通项 | $a_n=S_n-S_{n-1}$ | 仅 $n\ge2$，$n=1$ 单独验 |
| 裂项 | $\dfrac{1}{n(n+1)}=\dfrac1n-\dfrac{1}{n+1}$ | 求和后剩首尾两项 |
| 裂项（根式） | $\dfrac{1}{\sqrt{n+1}+\sqrt n}=\sqrt{n+1}-\sqrt n$ | 有理化后裂 |

## 五、立体几何

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 线面角 | $\sin\theta=\dfrac{|\vec a\cdot\vec n|}{|\vec a||\vec n|}$ | 用 $\sin$，不是 $\cos$ |
| 二面角 | $\cos\theta=\dfrac{\vec n_1\cdot\vec n_2}{|\vec n_1||\vec n_2|}$ | 结果要按图形判钝锐 |
| 点到面距离 | $d=\dfrac{|\vec{AP}\cdot\vec n|}{|\vec n|}$ | $\vec n$ 为平面法向量 |
| 柱体体积 | $V=Sh$ | |
| 锥体体积 | $V=\dfrac13Sh$ | |
| 球 | $S=4\pi R^2$，$V=\dfrac43\pi R^3$ | |

## 六、解析几何

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 两点距离 | $|AB|=\sqrt{(x_1-x_2)^2+(y_1-y_2)^2}$ | |
| 点到直线 | $d=\dfrac{|Ax_0+By_0+C|}{\sqrt{A^2+B^2}}$ | 直线要先化成一般式 |
| 弦长 | $|AB|=\sqrt{1+k^2}\,|x_1-x_2|$ | 竖直弦改用 $\sqrt{1+\frac{1}{k^2}}|y_1-y_2|$ |
| 椭圆 | $\dfrac{x^2}{a^2}+\dfrac{y^2}{b^2}=1$，$c^2=a^2-b^2$，$e=\dfrac ca$ | $a>b>0$ |
| 椭圆焦半径 | $|PF_1|=a+ex_0$，$|PF_2|=a-ex_0$ | 焦点在 $x$ 轴时 |
| 双曲线 | $\dfrac{x^2}{a^2}-\dfrac{y^2}{b^2}=1$，$c^2=a^2+b^2$，$e=\dfrac ca$ | 渐近线 $y=\pm\dfrac ba x$ |
| 抛物线 | $y^2=2px$，焦点 $\left(\dfrac p2,0\right)$，准线 $x=-\dfrac p2$ | 焦半径 $|PF|=x_0+\dfrac p2$ |
| 通径 | 椭圆/双曲线 $\dfrac{2b^2}{a}$；抛物线 $2p$ | |

## 七、概率统计

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 条件概率 | $P(B\mid A)=\dfrac{P(AB)}{P(A)}$ | $P(A)>0$ |
| 全概率 | $P(B)=\sum P(A_i)P(B\mid A_i)$ | $A_i$ 构成完备事件组 |
| 二项分布 | $E(X)=np$，$D(X)=np(1-p)$ | 独立重复，$p$ 每次相同 |
| 超几何 | $E(X)=\dfrac{nM}{N}$ | 不放回抽样 |
| 正态 | $P(\mu-\sigma<X\le\mu+\sigma)\approx0.6827$ | 三σ原则的近似值 |
| 独立性检验 | $K^2=\dfrac{n(ad-bc)^2}{(a+b)(c+d)(a+c)(b+d)}$ | 结论是"是否有证据"，不是"证明有关" |
| 回归系数 | $\hat b=\dfrac{\sum(x_i-\bar x)(y_i-\bar y)}{\sum(x_i-\bar x)^2}$ | 过样本中心点 $(\bar x,\bar y)$ |

## 八、向量

| 名称 | 公式 | 条件 / 易错 |
|---|---|---|
| 数量积 | $\vec a\cdot\vec b=|\vec a||\vec b|\cos\theta$ | $\theta\in[0,\pi]$ |
| 坐标数量积 | $\vec a\cdot\vec b=x_1x_2+y_1y_2$ | |
| 垂直 | $\vec a\perp\vec b\iff\vec a\cdot\vec b=0$ | |
| 平行 | $\vec a\parallel\vec b\iff x_1y_2-x_2y_1=0$ | 不是 $x_1x_2=y_1y_2$ |
| 模 | $|\vec a|=\sqrt{x^2+y^2}$ | |
