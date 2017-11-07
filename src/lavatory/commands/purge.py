"""Purges artifacts."""
import inspect
import logging

import click

from ..utils.artifactory import Artifactory
from ..utils.performance import get_performance_report
from ..utils.setup_pluginbase import setup_pluginbase, get_policy

LOG = logging.getLogger(__name__)


@click.command()
@click.pass_context
@click.option('--policies-path', required=False, help='Path to extra policies directory.')
@click.option(
    '--dryrun/--nodryrun', default=True, is_flag=True, help='Dryrun does not delete any artifacts. On by default.')
@click.option('--default/--no-default', default=True, is_flag=True, help='If false, does not apply default policy.')
@click.option(
    '--repo',
    default=None,
    multiple=True,
    required=False,
    help='Name of specific repository to run against. Can use --repo multiple times. If not provided, uses all repos.')
@click.option('--repo-type', default='local', required=False, type=click.Choice(['local', 'virtual', 'cache', 'any']),
              help="The types of repositories to search for. Local repositories by default.")
def purge(ctx, dryrun, policies_path, default, repo, repo_type):
    """Deletes artifacts based on retention policies."""
    LOG.debug('Passed args: %s, %s, %s, %s, %s, %s', ctx, dryrun, policies_path, default, repo, repo_type)
    artifactory = Artifactory(repo_name=None)
    before_purge_data = artifactory.list(repo_type=repo_type)
    if repo:
        selected_repos = rep
    else:
        selected_repos = before_purge_data.keys()

    apply_purge_policies(selected_repos, policies_path=policies_path, dryrun=dryrun, default=default)
    generate_purge_report(selected_repos, before_purge_data)

    LOG.info("Success.")
    return True


def apply_purge_policies(selected_repos, policies_path=None, dryrun=True, default=True):
    """Sets up the plugins to find purgable artifacts and delete them. 

    Args:
        selected_repos (list): List of repos to run against.
        policies_path (str): Path to extra policies
        dryrun (bool): If true, will not actually delete artifacts.
        default (bool): If true, applies default policy to repos with no specific policy.
    """
    plugin_source = setup_pluginbase(extra_policies_path=policies_path)
    LOG.info("Applying retention policies to %s", ', '.join(selected_repos))
    for repository in selected_repos:
        artifactory_repo = Artifactory(repo_name=repository)
        policy = get_policy(plugin_source, repository, default=default)
        if not policy:
            continue
        LOG.info("Policy Docs: %s", inspect.getdoc(policy.purgelist))
        artifacts = policy.purgelist(artifactory_repo)
        purged_count = artifactory_repo.purge(dryrun, artifacts)
        LOG.info("Processed %s, Purged %s", repository, purged_count)


def generate_purge_report(purged_repos, before_purge_data):
    """Generates a performance report based on deleted artifacts.

    Args:
        purged_repos (list): List of repos that had policy applied.
        before_purge_data (dict): Data on the state of Artifactory before purged artifacts
    """
    LOG.info("Purging Performance:")
    artifactory = Artifactory(repo_name=None)
    after_purge_data = artifactory.list()
    for repo, info in after_purge_data.items():
        if repo in purged_repos:
            try:
                get_performance_report(repo, before_purge_data[repo], info)
            except IndexError:
                pass
