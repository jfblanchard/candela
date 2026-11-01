# Maintainer: Jon Blanchard <https://github.com/jfblanchard>
pkgname=candela
pkgver=0.1.4
pkgrel=1
pkgdesc="Manual brightness and color temperature control for Linux"
arch=('any')
url="https://github.com/jfblanchard/candela"
license=('MIT')
depends=('python' 'python-pyqt6' 'redshift' 'xorg-xrandr' 'procps-ng')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=("https://files.pythonhosted.org/packages/source/c/candela-ctrl/candela_ctrl-${pkgver}.tar.gz")
sha256sums=('2dd3bbb5641aff98ae55ee80d2490014ffb5df2873a027b26bf641bae112e1fc')

build() {
    cd "candela_ctrl-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "candela_ctrl-${pkgver}"
    python -m installer --destdir="$pkgdir" dist/*.whl
}
