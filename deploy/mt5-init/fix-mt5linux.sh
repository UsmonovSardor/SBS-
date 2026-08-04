#!/usr/bin/env bash
# TITAN AI — gmag11/metatrader5_vnc konteynerini Python 3.11 mos qiladi.
#
# LSIO /custom-cont-init.d: konteyner init'ida (root), autostart -> start.sh
# ISHGA TUSHISHIDAN OLDIN ishlaydi. start.sh keyin mt5linux + numpy o'rnatadi;
# biz to'g'ri versiyalarni majburlaymiz (idempotent, har boot'da xavfsiz):
#
#   (1) Linux mt5linux -> 0.1.9. Sabab: gmag11 start.sh `-w wine python.exe`
#       CLI'sini kutadi (asl lucas-campagna). PyPI'dagi `pip install mt5linux`
#       endi BOSHQA paketni (1.1.0) beradi — u Python 3.12 f-string ishlatadi,
#       konteyner py3.11'da SyntaxError -> RPyC server (8001) ko'tarilmaydi.
#   (2) Wine numpy -> <2. Sabab: MetaTrader5==5.0.36 numpy 1.x ABI'ga qurilgan;
#       start.sh 2.x tortadi -> "numpy.core.multiarray failed to import".
#
# Bularsiz fresh (volume tozalangan) deploy ishlamaydi.
set -e
S=/Metatrader/start.sh
[ -f "$S" ] || { echo "[titan-init] $S topilmadi — o'tkazib yuborildi"; exit 0; }

# (1) Linux mt5linux'ni 0.1.9 ga pin qilamiz.
sed -i 's/--no-deps mt5linux \&\&/--no-deps mt5linux==0.1.9 \&\&/' "$S"

# (2) Wine numpy<2 ni server startidan oldin o'rnatamiz.
#     Delimiter @ — replacement ichida `||` (| belgisi) bor.
if ! grep -q 'TITAN_NUMPY_FIX' "$S"; then
  sed -i 's@# Start the MT5 server on Linux@# TITAN_NUMPY_FIX: MetaTrader5 5.0.36 uchun numpy 1.x kerak\n"$wine_executable" python -m pip install --no-cache-dir "numpy<2" || true\n\n# Start the MT5 server on Linux@' "$S"
fi

echo "[titan-init] start.sh tuzatildi: Linux mt5linux==0.1.9 + Wine numpy<2"
