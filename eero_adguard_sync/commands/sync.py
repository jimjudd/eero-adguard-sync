import click
from requests import HTTPError
from timeit import default_timer as timer

from eero_adguard_sync.client import EeroClient, AdGuardClient
from eero_adguard_sync.models import (
    AdGuardCredentialSet,
    AdGuardClientDevice,
    DHCPClientTable,
    DHCPClientTableDiff,
)


NETWORK_SELECT_PROMPT = """Multiple Eero networks found, please select by ID
                
{network_options}

Network ID"""


class EeroAdGuardSyncHandler:
    def __init__(
        self,
        eero_client: EeroClient,
        adguard_client: AdGuardClient,
        network_id: str = None,
        network_name: str = None,
        non_interactive: bool = False,
    ):
        self.eero_client = eero_client
        self.adguard_client = adguard_client
        self.__network = self.__prompt_network(network_id, network_name, non_interactive)

    @property
    def network(self) -> str:
        return self.__network

    def __prompt_network(
        self,
        network_id: str = None,
        network_name: str = None,
        non_interactive: bool = False,
    ) -> str:
        network_list = self.eero_client.account()["networks"]["data"]
        if not network_list:
            raise click.ClickException("No Eero networks associated with this account")

        if network_id:
            for network in network_list:
                if str(network["url"]) == str(network_id):
                    click.echo(f"Selected network '{network['name']}'")
                    return network["url"]
            raise click.ClickException(f"Eero network ID '{network_id}' was not found")

        if network_name:
            for network in network_list:
                if network["name"].strip().lower() == network_name.strip().lower():
                    click.echo(f"Selected network '{network['name']}'")
                    return network["url"]
            raise click.ClickException(
                f"Eero network named '{network_name}' was not found"
            )

        network_count = len(network_list)
        network_idx = 0
        if network_count > 1:
            if non_interactive:
                raise click.ClickException(
                    "Multiple Eero networks found. Set --eero-network-id or "
                    "--eero-network-name for unattended runs."
                )
            network_options = "\n".join(
                [f"{i}: {network['name']}" for i, network in enumerate(network_list)]
            )
            choice = click.Choice([str(i) for i in range(network_count)])
            network_idx = int(
                click.prompt(
                    NETWORK_SELECT_PROMPT.format(network_options=network_options),
                    type=choice,
                    default=str(network_idx),
                    show_choices=False,
                )
            )
        network = network_list[network_idx]
        click.echo(f"Selected network '{network['name']}'")
        return network["url"]

    def create(self, diff: DHCPClientTableDiff):
        if not diff.discovered:
            click.echo("No new clients found, skipped creation")
            return
        with click.progressbar(
            diff.discovered, label="Add new clients", show_pos=True
        ) as bar:
            duplicate_devices = []
            for eero_device in bar:
                new_device = AdGuardClientDevice.from_dhcp_client(eero_device)
                try:
                    self.adguard_client.add_client_device(new_device)
                except HTTPError as e:
                    response_text = (
                        e.response.text.strip() if e.response is not None else ""
                    )
                    lowered = response_text.lower()
                    if "same name" in lowered:
                        existing_client = next(
                            (
                                client
                                for client in self.adguard_client.get_clients()
                                if client.name == new_device.name
                            ),
                            None,
                        )
                        if existing_client is None:
                            raise click.ClickException(
                                "AdGuard reported a duplicate client name, but the "
                                f"existing client '{new_device.name}' could not be found."
                            ) from e
                        new_device.params = existing_client.params
                        self.adguard_client.update_client_device(
                            existing_client.name, new_device
                        )
                    elif any(
                        [
                            True
                            for error in [
                                "client already exists",
                                "another client uses the same id",
                                "already exists",
                            ]
                            if error.lower() in lowered
                        ]
                    ):
                        duplicate_devices.append(
                            f"'{eero_device.nickname}' [{eero_device.mac_address}]"
                        )
                    else:
                        raise click.ClickException(
                            "Failed to add AdGuard client "
                            f"'{eero_device.nickname}' "
                            f"[{eero_device.mac_address}]: "
                            f"{response_text or e}"
                        ) from e
            if duplicate_devices:
                for duplicate_device in duplicate_devices:
                    click.secho(
                        f"Skipped device, duplicate name in Eero network: {duplicate_device}",
                        fg="red",
                    )

    def update(self, diff: DHCPClientTableDiff):
        if not diff.associated:
            click.echo("No existing clients found, skipped update")
            return
        with click.progressbar(
            diff.associated, label="Update existing clients", show_pos=True
        ) as bar:
            for adguard_device, eero_device in bar:
                new_device = AdGuardClientDevice.from_dhcp_client(eero_device)
                new_device.params = adguard_device.instance.params
                self.adguard_client.update_client_device(
                    adguard_device.nickname, new_device
                )

    def delete(self, diff: DHCPClientTableDiff):
        if not diff.missing:
            click.echo("No removed clients found, skipped deletion")
            return
        with click.progressbar(
            diff.missing, label="Delete removed clients", show_pos=True
        ) as bar:
            for device in bar:
                self.adguard_client.remove_client_device(device.nickname)

    def sync(self, delete: bool = False, overwrite: bool = False):
        if overwrite:
            self.adguard_client.clear_clients()

        eero_clients = []
        for client in self.eero_client.get_clients(self.__network):
            try:
                eero_clients.append(client.to_dhcp_client())
            except ValueError:
                click.secho(
                    f"Eero device missing MAC address, skipped device named '{client.nickname}'",
                    fg="red",
                )
        eero_table = DHCPClientTable(eero_clients)

        adguard_clients = []
        for client in self.adguard_client.get_clients():
            try:
                adguard_clients.append(client.to_dhcp_client())
            except ValueError:
                click.secho(
                    f"AdGuard device missing MAC address, skipped device named '{client.name}'",
                    fg="red",
                )
        adguard_table = DHCPClientTable(adguard_clients)

        dhcp_diff = adguard_table.compare(eero_table)
        if not overwrite:
            self.update(dhcp_diff)
        self.create(dhcp_diff)
        if delete:
            self.delete(dhcp_diff)


@click.command()
@click.option(
    "--adguard-host",
    help="AdGuard Home host IP address",
    type=str,
    envvar="EAG_ADGUARD_HOST",
)
@click.option(
    "--adguard-user",
    help="AdGuard Home username",
    type=str,
    envvar="EAG_ADGUARD_USER",
)
@click.option(
    "--adguard-password",
    help="AdGuard Home password",
    type=str,
    envvar=["EAG_ADGUARD_PASSWORD", "EAG_ADGUARD_PASS"],
)
@click.option(
    "--eero-user",
    help="Eero email address or phone number",
    type=str,
    envvar="EAG_EERO_USER",
)
@click.option(
    "--eero-cookie",
    help="Eero session cookie",
    type=str,
    envvar="EAG_EERO_COOKIE",
)
@click.option(
    "--eero-network-id",
    help="Eero network ID/url to sync",
    type=str,
    envvar="EAG_EERO_NETWORK_ID",
)
@click.option(
    "--eero-network-name",
    help="Eero network name to sync",
    type=str,
    envvar="EAG_EERO_NETWORK_NAME",
)
@click.option(
    "--delete",
    "-d",
    is_flag=True,
    default=False,
    help="Delete AdGuard clients not found in Eero DHCP list",
    envvar="EAG_DELETE",
)
@click.option(
    "--confirm",
    "-y",
    is_flag=True,
    default=False,
    help="Skip interactive confirmation",
    envvar="EAG_CONFIRM",
)
@click.option(
    "--overwrite",
    "-o",
    is_flag=True,
    default=False,
    help="Delete all AdGuard clients before sync",
    envvar="EAG_OVERWRITE",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Display debug information",
    envvar="EAG_DEBUG",
)
def sync(
    adguard_host: str = None,
    adguard_user: str = None,
    adguard_password: str = None,
    eero_user: str = None,
    eero_cookie: str = None,
    eero_network_id: str = None,
    eero_network_name: str = None,
    delete: bool = False,
    confirm: bool = False,
    overwrite: bool = False,
    debug: bool = False,
    *args,
    **kwargs,
):
    if eero_network_id and eero_network_name:
        raise click.ClickException(
            "Use either --eero-network-id or --eero-network-name, not both."
        )

    # Eero auth
    eero_client = EeroClient(eero_cookie)
    if eero_client.needs_login():
        if confirm and not eero_user:
            raise click.ClickException(
                "Eero login is required. Set --eero-user or EAG_EERO_USER for "
                "the first unattended run."
            )
        if not eero_user:
            eero_user = click.prompt("Eero email address or phone number", type=str)
        click.echo("Authenticating Eero...")
        user_token = eero_client.login(eero_user)
        if confirm:
            raise click.ClickException(
                "Eero sent a verification code. Re-run interactively once to "
                "complete login and cache the session, or provide EAG_EERO_COOKIE."
            )
        verification_code = click.prompt("Verification code from email or SMS")
        click.echo("Verifying code...")
        eero_client.login_verify(verification_code, user_token)
        click.echo("Eero successfully authenticated")
    else:
        click.echo("Using cached Eero credentials")
    if debug:
        click.echo(f"Eero cookie value: {eero_client.session.cookie}")
        exit()

    # AdGuard auth
    if not adguard_host:
        adguard_host = click.prompt("AdGuard host IP address", type=str)
    adguard_client = AdGuardClient(adguard_host)
    if not adguard_user:
        adguard_user = click.prompt("AdGuard username", type=str)
    if not adguard_password:
        adguard_password = click.prompt("AdGuard password", type=str, hide_input=True)
    adguard_creds = AdGuardCredentialSet(adguard_user, adguard_password)
    click.echo("Authenticating AdGuard...")
    adguard_client.authenticate(adguard_creds)
    click.echo("AdGuard successfully authenticated")

    # Handle
    handler = EeroAdGuardSyncHandler(
        eero_client,
        adguard_client,
        network_id=eero_network_id,
        network_name=eero_network_name,
        non_interactive=confirm,
    )
    if overwrite:
        delete = False
    if not confirm:
        click.confirm(f"Sync this network?", abort=True)
        if overwrite:
            click.confirm(
                "WARNING: All clients in AdGuard will be deleted, confirm?", abort=True
            )
        if delete:
            click.confirm(
                "WARNING: Clients in AdGuard not found in Eero's DHCP list will be deleted, confirm?",
                abort=True,
            )
    click.echo("Starting sync...")
    start = timer()
    handler.sync(delete, overwrite)
    elapsed = timer() - start
    click.echo(f"Sync complete in {round(elapsed, 2)}s")
