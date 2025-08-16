# 🏖️ Calculate Tourist Taxes

> A Home Assistant integration to help you manage and calculate tourist taxes.  
> **⚠️ Currently in Beta – Use at your own risk!**

![Beta](https://img.shields.io/badge/status-beta-yellow)
![Made for Home Assistant](https://img.shields.io/badge/made%20for-Home%20Assistant-blue)

---

## 📚 Table of Contents

- [🏖️ Calculate Tourist Taxes](#️-calculate-tourist-taxes)
  - [📚 Table of Contents](#-table-of-contents)
  - [⚠️ Beta Notice](#️-beta-notice)
  - [❗ Disclaimer](#-disclaimer)
  - [📦 Installation](#-installation)
    - [Install using HACS:](#install-using-hacs)
  - [⚙️ Configuration](#️-configuration)
  - [Create two directories:](#create-two-directories)
  - [Create 2 New Files:](#create-2-new-files)
  - [🧼 Reset Button Example](#-reset-button-example)
  - [Add entry](#add-entry)
  - [Dashboard](#dashboard)
  - [Reload data](#reload-data)

---

## ⚠️ Beta Notice

This project is currently in **beta** and considered **unstable**.  
It is not production-ready and **should not be used in critical environments**.

---

## ❗ Disclaimer

By using this software — for example, to calculate tourist taxes — you do so **at your own risk**.  
The maintainers are **not responsible** for any fees, purchases, or issues that may arise.

Please use responsibly.

---

## 📦 Installation

### Install using HACS:

1. Go to **HACS** → **Custom Integrations**
2. Click the **3 dots** in the upper right corner
3. Search for `Touristtaxes`
4. Click **Custom Repositories**
5. Restart Home Assistant

## ⚙️ Configuration

Add the following to your `configuration.yaml` file:
```yaml
input_number:!include_dir_merge_named touristtaxes/input_number_touristtaxes<br>
input_datetime:!include_dir_merge_named touristtaxes/input_datetime_touristtaxes
```
## Create two directories:
```yaml
/config/touristtaxes/input_number_touristtaxes<br>
/config/touristtaxes/input_datetime_touristtaxes
```
## Create 2 New Files:
```yaml
/config/touristtaxes/input_number_touristtaxes/tourist_guests.yaml

and use this code:

tourist_guests:
  name: "Aantal logés"
  min: 0
  max: 10
  step: 1
  mode: box
  icon: mdi:account-group
```

```yaml
/config/touristtaxes/input_datetime_touristtaxes/tourist_tax_update_time.yaml

and use this code:

tourist_tax_update_time:
  name: "Toeristenbelasting Update Tijd"
  has_date: false
  has_time: true
  initial: "23:00"
  icon: mdi:clock-outline
```

## 🧼 Reset Button Example

To reset all data, add a **reset button** to your dashboard:

```yaml
show_name: true
show_icon: true
type: button
tap_action:
  action: call-service
  service: touristtaxes.reset_data
name: Reset Toeristenbelasting
icon: mdi:delete
grid_options:
  columns: 12
  rows: 2
```

## Add entry

Choose the price per person (default is 2.40)<br>
Choose the zone (default is zone.home)

## Dashboard

Create your own dashboard using the sensor enteties<br>
For changing the default time (e.g. input_datetime.tourist_tax_update_time)<br>
For changing the number of guests (input_number.tourist_guests)<br>
Anyone in the chosen zone is automatically included in the calculation

## Reload data

If you want to change the data in the JSON file just be careful and if you changed the file be sure to:<br>
Developer Tools - Actions - touristtaxes.reload_data hit the button **Perform action**