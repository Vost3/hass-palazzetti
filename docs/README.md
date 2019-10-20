# Custom component Palazzetti for Home assistant 
A Home Assistant component for manage your Palazzetti stove

## Installation
Create directory `custom_components` in your home assistant configs directory is not exist
Copy the `palazzetti` directory and its contents to your directory `custom_components`

It should look similar to this after installation:
```
.homeassistant/
|-- custom_components/
|   |-- palazzetti/
|       |-- __init__.py
|       |-- manifest.json
```

## Configuration
Declare the component `palazzetti` in your configuration.yaml file.
Follow the sample below

ip = Ip of your Cbox

### Declaration `configuration.yaml`
```yaml
palazzetti:
  ip: 192.168.1.1    
```

## Parameters
| name       | type      | mandatory | description |
|:-----------|:----------|:----------|:------------|
| `ip`       | str       | yes       | local ip of your cbox |


### Service
You can set some parameters through the service `palazzetti.set_parms`
<img src="assets/service_call_1.png" alt="Palazzetti Service call"></a>

### Automation
```yaml
- id: '1'
  alias: Check pwr state
  trigger:
    platform: state
    entity_id: palazzetti.stove
  action:
  - service: input_text.set_value    
    data_template:
      entity_id: input_text.text_test # don't miss to create a input_text "text_test" for test this script
      value: "{{ state_attr('palazzetti.stove', 'PWR') }}"
```

### Template
```yaml
    data_template:
      entity_id: input_text.text_test
      value: "{{ state_attr('palazzetti.stove', 'PWR') }}"
```

### Script
```yaml
'1': # set Fan Room
  alias: Test - set FAN Room
  sequence:  
  - service: palazzetti.set_parms    
    data:
      RFAN: 3

'2': # set fire power
  alias: Test - set fire Power
  sequence:  
  - service: palazzetti.set_parms    
    data:
      PWR: 3

'3': # start or stop stop
  alias: Test - Start stove
  sequence:  
  - service: palazzetti.set_parms    
    data:
      STATUS: ON
```

## Data Parameters
Here all parameters that can be changed

| name       | type      | possible values             | description 			 |
|:-----------|:----------|:----------------------------|:------------------------|
| `SETP`     | int       |                             | temperature target 	 |
| `PWR`      | int       |  1 to 5                     | fire power 			 |
| `RFAN`     | int & str |  off / 1 to 5 / auto / high | level of room fan 		 |
| `STATUS`   | str       |  on / off                   | start or stop the stove |

## Other
### Note
This component is tested only on Stove `NINA 6kW` not ductable. Don't hesitate to signal any trouble
I know some difference for other stove that have the option ductable

### Coming soon
- [ ] fix for ductable stove
- [ ] named vars for PWR / RFAN / SETP
- [ ] link with `climate` entity
- [ ] may be an updater for check new release of component

#### DEV - enable log
Enable home-assistant logger in your `configuration.yaml`
```yaml
logger:
  default: error  
  logs:    
    custom_components.palazzetti: debug
```
