# Maintainer: Jon Blanchard <https://github.com/jfblanchard>
pkgname=candela
pkgver=0.1.6
pkgrel=1
pkgdesc="Manual brightness and color temperature control for Linux"
arch=('any')
url="https://github.com/jfblanchard/candela"
license=('MIT')
depends=('python' 'python-pyqt6' 'redshift' 'xorg-xrandr' 'procps-ng')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=("https://files.pythonhosted.org/packages/source/c/candela-ctrl/candela_ctrl-${pkgver}.tar.gz")
sha256sums=('a2e8e4953140b72de2b5b566dfb93448f2bf774a86c510c316508a954f955815')

build() {
    cd "candela_ctrl-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "candela_ctrl-${pkgver}"
    python -m installer --destdir="$pkgdir" dist/*.whl
}
