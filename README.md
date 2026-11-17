# Sharp Memory LCD na Raspberry Pi – demo „nazdar“

*English summary: a minimal demo that prints "nazdar" on a 2.7" Sharp Memory LCD
(LS027B7DH01, 400×240) attached to a Raspberry Pi over SPI, using the
[sharp-drm](https://github.com/ardangelo/sharp-drm-driver) kernel driver. Instructions below are in Czech.*

Malý program, který napíše na displej **Sharp Memory LCD 2,7"** slovo **nazdar**.
Slouží jako první krok: když se nápis objeví, je displej zapojený a ovladač funguje.

## Co je potřeba

- Raspberry Pi s 40pinovým konektorem. **Ověřeno na Raspberry Pi Zero 2 W**
  s Raspberry Pi OS (Debian 13 „trixie“, 64 bit). Na jiných modelech to nemusí fungovat
  stejně – hlavně **Raspberry Pi 5 není vyzkoušené** (má jiný řadič SPI).
- Displej **Sharp Memory LCD 2,7"**, panel **LS027B7DH01**, 400×240, černobílý
  (např. modul od LaskaKit).
- Internet (kvůli stažení ovladače) a asi 15 minut.

## Proč je to jiné než běžný displej

Memory LCD si každý pixel pamatuje sám, takže skoro nic nežere a je dobře čitelný na slunci.
Má ale jednu zvláštnost: **potřebuje neustále přepínat polaritu (signál VCOM, asi 1×
za sekundu)**. Bez toho se panel časem poškodí. Tohle obstarává ovladač `sharp-drm` sám –
proto se displej nemá nechávat zapnutý bez načteného ovladače.

## 1) Zapojení

Zapojení odpovídá souboru [`sharp-drm.dts`](sharp-drm.dts) v tomto repozitáři (ověřeno na
běžícím Raspberry Pi Zero 2 W):

| Displej | Raspberry Pi | Fyzický pin |
|---|---|---|
| VIN / VDD | 3,3 V | 1 |
| GND | GND | 6 |
| SCLK (CLK) | GPIO11 (SPI0 SCLK) | 23 |
| MOSI (DI) | GPIO10 (SPI0 MOSI) | 19 |
| CS (SCS) | GPIO25 | 22 |
| EXTCOMIN (VCOM) | GPIO23 | 16 |
| DISP | GPIO22 | 15 |

MISO se nepoužívá, displej data jen přijímá. Pozor: **CS je u tohoto displeje aktivní
v log. 1** (obráceně než u většiny SPI zařízení) – ovladač to řeší sám.

> **Pozor na rozdíl oproti originálnímu ovladači:** `sharp-drm.dts` přímo v repozitáři
> sharp-drm-driver má CS na GPIO8 (pin 24). Tenhle návod používá **upravený overlay s CS na
> GPIO25** – proto se v kroku 3 kompiluje `sharp-drm.dts` z tohoto repozitáře, ne z ovladače.
> Pokud chceš zapojit CS na GPIO8, použij overlay z ovladače.

## 2) Instalace ovladače

```bash
sudo apt update
sudo apt install -y git build-essential linux-headers-rpi-v8 device-tree-compiler python3-pil fonts-dejavu-core
cd ~
git clone https://github.com/BorisYurinov/sharp-lcd-demo.git
git clone https://github.com/ardangelo/sharp-drm-driver.git
cd sharp-drm-driver
make
sudo make install
```

`linux-headers-rpi-v8` platí pro 64bitový systém na Zero 2 W, Pi 3 a Pi 4. Pokud `make`
skončí chybou o chybějících hlavičkách jádra, nejdřív `sudo apt full-upgrade` a restart, ať
hlavičky odpovídají běžícímu jádru (`uname -r`).

`sudo make install` přidá do `/etc/modules` řádek `sharp-drm`, takže se ovladač načte při každém startu.

## 3) Nastavení systému

Nejdřív záloha:

```bash
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.zaloha
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.zaloha
```

Ovladač si overlay (popis zapojení pro jádro) neinstaluje sám, proto zkompiluj a zkopíruj
overlay z tohoto repozitáře a zapni ho v `/boot/firmware/config.txt` (dvě varování
`unit_address_vs_reg` při kompilaci jsou neškodná):

```bash
cd ~/sharp-lcd-demo
dtc -@ -I dts -O dtb -o sharp-drm.dtbo sharp-drm.dts
sudo cp sharp-drm.dtbo /boot/firmware/overlays/
echo "dtparam=spi=on" | sudo tee -a /boot/firmware/config.txt
echo "dtoverlay=sharp-drm" | sudo tee -a /boot/firmware/config.txt
```

Do `/boot/firmware/cmdline.txt` přidej **na konec téhož jediného řádku** (nesmí vzniknout nový řádek):

```
fbcon=map:1 fbcon=font:VGA8x16
```

`map:1` znamená framebuffer č. 1 – na Zero 2 W je `fb0` HDMI a displej dostane `fb1` (ověř po restartu přes `cat /sys/class/graphics/fb1/name`). Tohle přesměruje textovou konzoli na displej. **Bez toho ovladač displej nikdy nezapne**
(a nespustí ani přepínání VCOM) – to je nejčastější důvod, proč displej zůstane prázdný.

Pak restart:

```bash
sudo reboot
```

Po startu by se na displeji měla objevit textová konzole s přihlášením.

## 4) Spuštění dema

```bash
cd ~/sharp-lcd-demo
python3 nazdar.py
```

Vlastní text: `python3 nazdar.py "Ahoj světe"`.

Program si framebuffer displeje najde sám podle jména (`sharp`). Uživatel musí být ve skupině
`video` (výchozí uživatel na Raspberry Pi OS v ní je).

Textová konzole kreslí do stejného framebufferu, takže blikající kurzor nebo nový výpis může
nápis časem přepsat. Pro demo je nejjednodušší spustit program přes SSH.

## Když to nefunguje

```bash
lsmod | grep sharp                      # je ovladač načtený?
dmesg | grep -i sharp                   # hlášky ovladače
cat /sys/class/graphics/fb*/name        # existuje framebuffer "sharp_drmdrmfb"?
cat /sys/class/vtconsole/vtcon1/bind    # 1 = konzole je na displeji namapovaná
```

| Příznak | Pravděpodobná příčina |
|---|---|
| `lsmod` nic neukáže | ovladač se nenainstaloval – zopakuj krok 2 |
| framebuffer existuje, displej prázdný | chybí `fbcon=map:1` v `cmdline.txt` (krok 3) |
| obraz je inverzní | `echo 1 \| sudo tee /sys/module/sharp_drm/parameters/mono_invert` |

Hláška `sharp_drm@0 GPIO handle specifies active low - ignored` v `dmesg` je neškodná: overlay
deklaruje CS zároveň jako aktivní low (`cs-gpios`) i aktivní high (`spi-cs-high`) a jádro se řídí tím druhým.

## Licence

Tohle demo (`nazdar.py`): MIT (viz `LICENSE`). Soubor `sharp-drm.dts` je upravený overlay
z projektu sharp-drm-driver, a proto spadá pod jeho licenci GPL-2.0. Samotný ovladač `sharp-drm` je samostatný projekt pod licencí GPL-2.0
a v tomto repozitáři není – stahuje se z [ardangelo/sharp-drm-driver](https://github.com/ardangelo/sharp-drm-driver).
