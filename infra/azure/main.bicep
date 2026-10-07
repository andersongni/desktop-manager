@description('Prefixo dos recursos (letras/números, curto).')
param namePrefix string = 'dmtest'

@description('Região Azure. Prefira uma com Standard_B2ats_v2 disponível (ex.: eastus, westus2, brazilsouth).')
param location string = resourceGroup().location

@description('Usuário administrador local da VM (RDP).')
param adminUsername string = 'dmadmin'

@description('Senha do administrador (mín. 12 caracteres, complexidade Azure).')
@secure()
param adminPassword string

@description('Tamanho da VM. Free trial (12 meses): Standard_B2ats_v2 / Standard_B2pts_v2 / Standard_B2ts_v2. Alternativas: B1s/B2s ou D2s_v3 se a série B estiver sem cota/capacidade.')
@allowed([
  'Standard_B2ats_v2'
  'Standard_B2ts_v2'
  'Standard_B2pts_v2'
  'Standard_B1s'
  'Standard_B2s'
  'Standard_B1ms'
  'Standard_D2s_v3'
  'Standard_D2s_v4'
  'Standard_D2s_v5'
  'Standard_A2_v2'
])
param vmSize string = 'Standard_D2s_v4'

@description('CIDR permitido para RDP (ex.: 203.0.113.10/32). Use * só em testes e restrinja depois.')
param allowedRdpSource string = '*'

@description('Fuso do auto-shutdown (Windows time zone id).')
param autoShutdownTimeZone string = 'E. South America Standard Time'

@description('Horário diário de desligamento (HHmm, fuso acima).')
param autoShutdownTime string = '2200'

@description('Baixar a última release do Desktop Manager na primeira boot.')
param bootstrapDesktopManager bool = true

@description('Repositório GitHub owner/name das releases.')
param githubRepo string = 'andersongni/desktop-manager'

@description('URL do bootstrap.ps1 (raw do GitHub). Após o push, use a branch main.')
param bootstrapScriptUri string = 'https://raw.githubusercontent.com/andersongni/desktop-manager/main/infra/azure/bootstrap.ps1'

var vmName = '${namePrefix}-vm'
var nicName = '${namePrefix}-nic'
var nsgName = '${namePrefix}-nsg'
var pipName = '${namePrefix}-pip'
var vnetName = '${namePrefix}-vnet'
var diskName = '${namePrefix}-osdisk'

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: nsgName
  location: location
  properties: {
    securityRules: [
      {
        name: 'Allow-RDP'
        properties: {
          priority: 1000
          access: 'Allow'
          direction: 'Inbound'
          protocol: 'Tcp'
          sourceAddressPrefix: allowedRdpSource
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '3389'
          description: 'RDP para teste do Desktop Manager'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.60.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'default'
        properties: {
          addressPrefix: '10.60.1.0/24'
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
    ]
  }
}

resource pip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: pipName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    idleTimeoutInMinutes: 4
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: nicName
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          publicIPAddress: {
            id: pip.id
          }
        }
      }
    ]
    networkSecurityGroup: {
      id: nsg.id
    }
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: vmName
  location: location
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: {
        secureBootEnabled: true
        vTpmEnabled: true
      }
    }
    osProfile: {
      computerName: take(replace(vmName, '-', ''), 15)
      adminUsername: adminUsername
      adminPassword: adminPassword
      windowsConfiguration: {
        provisionVMAgent: true
        enableAutomaticUpdates: true
        timeZone: autoShutdownTimeZone
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'MicrosoftWindowsDesktop'
        offer: 'windows-11'
        sku: 'win11-24h2-pro'
        version: 'latest'
      }
      osDisk: {
        name: diskName
        caching: 'ReadWrite'
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
        diskSizeGB: 128
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
}

resource autoShutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${vmName}'
  location: location
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: {
      time: autoShutdownTime
    }
    timeZoneId: autoShutdownTimeZone
    targetResourceId: vm.id
    notificationSettings: {
      status: 'Disabled'
    }
  }
}

resource bootstrap 'Microsoft.Compute/virtualMachines/extensions@2024-07-01' = if (bootstrapDesktopManager) {
  parent: vm
  name: 'BootstrapDesktopManager'
  location: location
  properties: {
    publisher: 'Microsoft.Compute'
    type: 'CustomScriptExtension'
    typeHandlerVersion: '1.10'
    autoUpgradeMinorVersion: true
    settings: {
      fileUris: [
        bootstrapScriptUri
      ]
    }
    protectedSettings: {
      commandToExecute: 'powershell -ExecutionPolicy Bypass -Command "$env:DM_GITHUB_REPO=\'${githubRepo}\'; & .\\bootstrap.ps1"'
    }
  }
}

output vmName string = vm.name
output adminUsername string = adminUsername
output publicIpName string = pip.name
output publicIpAddress string = pip.properties.ipAddress
output resourceGroupName string = resourceGroup().name
output rdpCommand string = 'mstsc /v:${pip.properties.ipAddress}'
output autoShutdown string = 'Desliga todo dia às ${autoShutdownTime} (${autoShutdownTimeZone}) com deallocate.'
