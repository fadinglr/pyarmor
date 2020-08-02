#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
#############################################################
#                                                           #
#      Copyright @ 2018 -  Dashingsoft corp.                #
#      All rights reserved.                                 #
#                                                           #
#      pyarmor                                              #
#                                                           #
#      Version: 3.4.0 -                                     #
#                                                           #
#############################################################
#
#
#  @File: pyarmor.py
#
#  @Author: Jondy Zhao(jondy.zhao@gmail.com)
#
#  @Create Date: 2018/01/17
#
#  @Description:
#
#   A tool used to import or run obfuscated python scripts.
#

'''PyArmor is a command line tool used to obfuscate python scripts,
bind obfuscated scripts to fixed machine or expire obfuscated scripts.

'''

import logging
import os
import shutil
import subprocess
import sys
import time

# argparse is new in Python 2.7, and not in 3.0, 3.1
# Besides no command aliases supported by Python 2.7
import polyfills.argparse as argparse

from config import version, version_info, purchase_info, \
                   config_filename, capsule_filename, license_filename


from project import Project
from utils import make_capsule, make_runtime, relpath, make_bootstrap_script,\
                  make_license_key, make_entry, show_hd_info, \
                  build_path, make_project_command, get_registration_code, \
                  pytransform_bootstrap, encrypt_script, search_plugins, \
                  get_product_key, register_keyfile, query_keyinfo, \
                  get_platform_list, download_pytransform, update_pytransform,\
                  check_cross_platform, compatible_platform_names, \
                  get_name_suffix, get_bind_key, make_super_bootstrap, \
                  make_protection_code, DEFAULT_CAPSULE, PYARMOR_PATH

import packer


def arcommand(func):
    return func


def _format_entry(entry, src):
    if entry:
        result = []
        for x in entry.split(','):
            x = x.strip()
            if os.path.exists(os.path.join(src, x)):
                result.append(relpath(os.path.join(src, x), src))
            elif os.path.exists(x):
                result.append(relpath(os.path.abspath(x), src))
            else:
                raise RuntimeError('No entry script %s found' % x)
        return ','.join(result)


@arcommand
def _init(args):
    '''Create a project to manage the obfuscated scripts.'''
    path = os.path.normpath(args.project)

    logging.info('Create project in %s ...', path)
    if os.path.exists(os.path.join(path, config_filename)):
        raise RuntimeError('A project already exists in "%s"' % path)
    if not os.path.exists(path):
        logging.info('Make project directory %s', path)
        os.makedirs(path)

    if os.path.isabs(args.src):
        pro_src = src = os.path.normpath(args.src)
    else:
        src = os.path.abspath(args.src)
        pro_src = relpath(src, path)
    logging.info('Python scripts base path: %s', src)
    logging.info('Project src is: %s', pro_src)

    if args.entry:
        args.entry = _format_entry(args.entry, src)
        logging.info('Format entry: %s', args.entry)

    name = os.path.basename(os.path.abspath(path))
    if (args.type == 'pkg') or \
       (args.type == 'auto' and os.path.exists(os.path.join(src,
                                                            '__init__.py'))):
        logging.info('Project is configured as package')
        if args.entry is None:
            logging.info('Entry script is set to "__init__.py" implicitly')
        project = Project(name=name, title=name, src=pro_src, is_package=1,
                          entry='__init__.py' if args.entry is None
                          else args.entry)
    else:
        logging.info('Project is configured as standalone application.')
        project = Project(name=name, title=name, src=pro_src, entry=args.entry)

    logging.info('Create configure file ...')
    filename = os.path.join(path, config_filename)
    project.save(path)
    logging.info('Configure file %s created', filename)

    if sys.argv[0] == 'pyarmor.py':
        logging.info('Create pyarmor command ...')
        platname = sys.platform
        s = make_project_command(platname, sys.executable, sys.argv[0], path)
        logging.info('PyArmor command %s created', s)

    logging.info('Project init successfully.')


@arcommand
def _config(args):
    '''Update project settings.'''
    for x in ('obf-module-mode', 'obf-code-mode', 'disable-restrict-mode'):
        if getattr(args, x.replace('-', '_')) is not None:
            logging.warning('Option --%s has been deprecated', x)

    project = Project()
    project.open(args.project)
    logging.info('Update project %s ...', args.project)

    def _relpath(p):
        return p if os.path.isabs(p) \
            else relpath(os.path.abspath(p), project._path)

    if args.src is not None:
        args.src = _relpath(args.src)
        logging.info('Format src to %s', args.src)
    if args.output is not None:
        args.output = _relpath(args.output)
        logging.info('Format output to %s', args.output)
    if args.license_file is not None:
        args.license_file = _relpath(args.license_file)
        logging.info('Format license file to %s', args.license_file)
    if args.entry:
        src = os.path.abspath(args.src) if args.src else project.src
        args.entry = _format_entry(args.entry, src)
        logging.info('Format entry: %s', args.entry)
    if args.capsule is not None:
        logging.warning('The capsule %s is ignored', args.capsule)
    if args.plugins is not None:
        if ('clear' in args.plugins) or ('' in args.plugins):
            logging.info('Clear all plugins')
            args.plugins = []
    if args.platforms is not None:
        if '' in args.platforms:
            logging.info('Clear platforms')
            args.platform = ''
        else:
            args.platform = ','.join(args.platforms)
    if args.disable_restrict_mode is not None:
        if args.restrict_mode is not None:
            logging.warning('Option --disable_restrict_mode is ignored')
        else:
            args.restrict_mode = 0 if args.disable_restrict_mode else 1
    keys = project._update(dict(args._get_kwargs()))
    for k in keys:
        logging.info('Change project %s to "%s"', k, getattr(project, k))

    if keys:
        project.save(args.project)
        logging.info('Update project OK.')
    else:
        logging.info('Nothing changed.')


@arcommand
def _info(args):
    '''Show project information.'''
    project = Project()
    project.open(args.project)
    logging.info('Project %s information\n%s', args.project, project.info())


@arcommand
def _build(args):
    '''Build project, obfuscate all scripts in the project.'''
    project = Project()
    project.open(args.project)
    logging.info('Build project %s ...', args.project)

    logging.info('Check project')
    project.check()

    suffix = get_name_suffix() if project.get('enable_suffix', 0) else ''
    capsule = project.get('capsule', DEFAULT_CAPSULE)
    logging.info('Use capsule: %s', capsule)

    output = project.output if args.output is None \
        else os.path.normpath(args.output)
    logging.info('Output path is: %s', output)

    if args.platforms:
        platforms = [] if '' in args.platforms else args.platforms
    elif project.get('platform'):
        platforms = project.get('platform').split(',')
    else:
        platforms = []

    restrict = project.get('restrict_mode',
                           0 if project.get('disable_restrict_mode') else 1)
    advanced = (project.advanced_mode if project.advanced_mode else 0) \
        if hasattr(project, 'advanced_mode') else 0
    supermode = advanced in (2, 4)
    vmenabled = advanced in (3, 4)

    platforms = compatible_platform_names(platforms)
    logging.info('Taget platforms: %s', platforms)
    platforms = check_cross_platform(platforms, supermode, vmenabled)
    if platforms is False:
        return

    protection = project.cross_protection \
        if hasattr(project, 'cross_protection') else 1

    bootstrap_code = project.get('bootstrap_code', 1)
    relative = True if bootstrap_code == 3 else \
        False if (bootstrap_code == 2 or
                  (args.no_runtime and bootstrap_code == 1)) else None

    if args.no_runtime:
        if protection == 1:
            logging.warning('No cross protection because no runtime generated')
            protection = 0
    else:
        routput = output if args.output is not None and args.only_runtime \
            else os.path.join(output, os.path.basename(project.src)) \
            if project.get('is_package') else output
        if not os.path.exists(routput):
            logging.info('Make path: %s', routput)
            os.makedirs(routput)

        package = project.get('package_runtime', 0) \
            if args.package_runtime is None else args.package_runtime

        licfile = args.license_file if args.license_file is not None \
            else project.license_file
        if not restrict and not licfile:
            licfile = 'no-restrict'

        checklist = make_runtime(capsule, routput, licfile=licfile,
                                 platforms=platforms, package=package,
                                 suffix=suffix, supermode=supermode)

        if protection == 1:
            protection = make_protection_code(
                (relative, checklist, suffix),
                multiple=len(platforms) > 1,
                supermode=supermode)

    if not args.only_runtime:
        src = project.src
        if os.path.abspath(output).startswith(src):
            excludes = ['prune %s' % os.path.abspath(output)[len(src)+1:]]
        else:
            excludes = []

        files = project.get_build_files(args.force, excludes=excludes)
        soutput = os.path.join(output, os.path.basename(src)) \
            if project.get('is_package') else output

        logging.info('Save obfuscated scripts to "%s"', soutput)
        if not os.path.exists(soutput):
            os.makedirs(soutput)

        logging.info('Read public key from capsule')
        prokey = get_product_key(capsule)

        logging.info('%s increment build',
                     'Disable' if args.force else 'Enable')
        logging.info('Search scripts from %s', src)

        logging.info('Obfuscate scripts with mode:')
        if hasattr(project, 'obf_mod'):
            obf_mod = project.obf_mod
        else:
            obf_mod = project.obf_module_mode == 'des'
        if hasattr(project, 'wrap_mode'):
            wrap_mode = project.wrap_mode
            obf_code = project.obf_code
        elif project.obf_code_mode == 'wrap':
            wrap_mode = 1
            obf_code = 1
        else:
            wrap_mode = 0
            obf_code = 0 if project.obf_code_mode == 'none' else 1

        def v(t):
            return 'on' if t else 'off'
        logging.info('Obfuscating the whole module is %s', v(obf_mod))
        logging.info('Obfuscating each function is %s', v(obf_code))
        logging.info('Autowrap each code object mode is %s', v(wrap_mode))
        logging.info('Restrict mode is %s', restrict)
        logging.info('Advanced value is %s', advanced)
        logging.info('Super mode is %s', v(supermode))

        entries = [build_path(s.strip(), project.src)
                   for s in project.entry.split(',')] if project.entry else []
        adv_mode2 = (advanced - 2) if advanced > 2 else advanced

        for x in sorted(files):
            a, b = os.path.join(src, x), os.path.join(soutput, x)
            logging.info('\t%s -> %s', x, relpath(b))

            d = os.path.dirname(b)
            if not os.path.exists(d):
                os.makedirs(d)

            if hasattr(project, 'plugins'):
                plugins = search_plugins(project.plugins)
            else:
                plugins = None

            if entries and (os.path.abspath(a) in entries):
                adv_mode = adv_mode2 | 8
                pcode = protection
            else:
                adv_mode = adv_mode2
                pcode = 0

            encrypt_script(prokey, a, b, obf_code=obf_code, obf_mod=obf_mod,
                           wrap_mode=wrap_mode, adv_mode=adv_mode,
                           rest_mode=restrict, protection=pcode,
                           platforms=platforms, plugins=plugins,
                           rpath=project.runtime_path, suffix=suffix)

            if supermode:
                make_super_bootstrap(a, b, soutput, relative, suffix=suffix)

        logging.info('%d scripts has been obfuscated', len(files))
        project['build_time'] = time.time()
        project.save(args.project)

        if (not supermode) and project.entry and bootstrap_code:
            soutput = os.path.join(output, os.path.basename(project.src)) \
                if project.get('is_package') else output
            make_entry(project.entry, project.src, soutput,
                       rpath=project.runtime_path, relative=relative,
                       suffix=suffix)

    logging.info('Build project OK.')


def licenses(name='reg-001', expired=None, bind_disk=None, bind_mac=None,
             bind_ipv4=None, bind_data=None, key=None, home=None):
    if home:
        _change_home_path(home)
    else:
        _clean_home_path()

    pytransform_bootstrap()

    capsule = DEFAULT_CAPSULE
    if not os.path.exists(capsule):
        make_capsule(capsule)

    fmt = '' if expired is None else '*TIME:%.0f\n' % (
        expired if isinstance(expired, (int, float))
        else float(expired) if expired.find('-') == -1
        else time.mktime(time.strptime(expired, '%Y-%m-%d')))

    if bind_disk:
        fmt = '%s*HARDDISK:%s' % (fmt, bind_disk)

    if bind_mac:
        fmt = '%s*IFMAC:%s' % (fmt, bind_mac)

    if bind_ipv4:
        fmt = '%s*IFIPV4:%s' % (fmt, bind_ipv4)

    fmt = fmt + '*CODE:'
    extra_data = '' if bind_data is None else (';' + bind_data)

    return make_license_key(capsule, fmt + name + extra_data, key=key)


@arcommand
def _licenses(args):
    '''Generate licenses for obfuscated scripts.'''
    for x in ('bind-file',):
        if getattr(args, x.replace('-', '_')) is not None:
            logging.warning('Option --%s has been deprecated', x)

    capsule = DEFAULT_CAPSULE if args.capsule is None else args.capsule
    if not os.path.exists(capsule):
        logging.info('Generating public capsule ...')
        make_capsule(capsule)

    if os.path.exists(os.path.join(args.project, config_filename)):
        logging.info('Generate licenses for project %s ...', args.project)
        project = Project()
        project.open(args.project)
    else:
        if args.project != '':
            logging.warning('Ignore option --project, there is no project')
        logging.info('Generate licenses with capsule %s ...', capsule)
        project = dict(restrict_mode=args.restrict)

    output = args.output
    licpath = os.path.join(args.project, 'licenses') if output is None \
        else os.path.dirname(output) if output.endswith(license_filename) \
        else output
    if os.path.exists(licpath):
        logging.info('Output path of licenses: %s', licpath)
    elif licpath not in ('stdout', 'stderr'):
        logging.info('Make output path of licenses: %s', licpath)
        os.mkdir(licpath)

    fmt = '' if args.expired is None else '*TIME:%.0f\n' % (
        float(args.expired) if args.expired.find('-') == -1
        else time.mktime(time.strptime(args.expired, '%Y-%m-%d')))

    flags = 0
    restrict_mode = 0 if args.disable_restrict_mode else args.restrict
    period_mode = 1 if args.enable_period_mode else 0
    if restrict_mode:
        logging.info('The license file is generated in restrict mode')
    else:
        logging.info('The license file is generated in restrict mode disabled')
        flags |= 1
    if period_mode:
        logging.info('The license file is generated in period mode')
        flags |= 2
    else:
        logging.info('The license file is generated in period mode disabled')

    if flags:
        fmt = '%s*FLAGS:%c' % (fmt, chr(flags))

    if args.bind_disk:
        fmt = '%s*HARDDISK:%s' % (fmt, args.bind_disk)

    if args.bind_mac:
        fmt = '%s*IFMAC:%s' % (fmt, args.bind_mac)

    if args.bind_ipv4:
        fmt = '%s*IFIPV4:%s' % (fmt, args.bind_ipv4)

    # if args.bind_ipv6:
    #     fmt = '%s*IFIPV6:%s' % (fmt, args.bind_ipv6)

    if args.bind_domain:
        fmt = '%s*DOMAIN:%s' % (fmt, args.bind_domain)

    if args.fixed:
        keylist = args.fixed.split(',')
        if keylist[0] in ('1', ''):
            keylist[0] = '0123456789'
        fmt = '%s*FIXKEY:%s;' % (fmt, ','.join(keylist))

    if args.bind_file:
        if args.bind_file.find(';') == -1:
            bind_file, target_file = args.bind_file, ''
        else:
            bind_file, target_file = args.bind_file.split(';', 2)
        bind_key = get_bind_key(bind_file)
        fmt = '%s*FIXKEY:%s;%s;' % (fmt, target_file, bind_key)

    # Prefix of registration code
    fmt = fmt + '*CODE:'
    extra_data = '' if args.bind_data is None else (';' + args.bind_data)

    if not args.codes:
        args.codes = ['regcode-01']

    for rcode in args.codes:
        if args.output in ('stderr', 'stdout'):
            licfile = args.output
        elif args.output and args.output.endswith(license_filename):
            licfile = args.output
        else:
            output = os.path.join(licpath, rcode)
            if not os.path.exists(output):
                logging.info('Make path: %s', output)
                os.mkdir(output)
            licfile = os.path.join(output, license_filename)
        licode = fmt + rcode + extra_data
        txtinfo = licode.replace('\n', r'\n')
        if args.expired:
            txtinfo = '"Expired:%s%s"' % (args.expired,
                                          txtinfo[txtinfo.find(r'\n')+2:])
        logging.info('Generate license: %s', txtinfo)
        make_license_key(capsule, licode, licfile)
        logging.info('Write license file: %s', licfile)

        if licfile not in ('stderr', 'stdout'):
            logging.info('Write information to %s.txt', licfile)
            with open(os.path.join(licfile + '.txt'), 'w') as f:
                f.write(txtinfo)

    logging.info('Generate %d licenses OK.', len(args.codes))


@arcommand
def _capsule(args):
    '''Generate public capsule explicitly.'''
    capsule = os.path.join(args.path, capsule_filename)
    if args.force or not os.path.exists(capsule):
        logging.info('Generating public capsule ...')
        make_capsule(capsule)
    else:
        logging.info('Do nothing, capsule %s has been exists', capsule)


@arcommand
def _obfuscate(args):
    '''Obfuscate scripts without project.'''
    advanced = args.advanced if args.advanced else 0
    supermode = advanced in (2, 4)
    vmenabled = advanced in (3, 4)
    restrict = args.restrict

    platforms = compatible_platform_names(args.platforms)
    logging.info('Target platforms: %s', platforms if platforms else 'Native')
    platforms = check_cross_platform(platforms, supermode, vmenabled)
    if platforms is False:
        return

    for x in ('entry',):
        if getattr(args, x.replace('-', '_')) is not None:
            logging.warning('Option --%s has been deprecated', x)

    if args.src is None:
        if args.scripts[0].lower().endswith('.py'):
            path = os.path.abspath(os.path.dirname(args.scripts[0]))
        else:
            path = os.path.abspath(args.scripts[0])
            args.src = path
            if len(args.scripts) > 1:
                raise RuntimeError('Only one path is allowed')
            args.scripts = []
    else:
        for s in args.scripts:
            if not s.lower().endswith('.py'):
                raise RuntimeError('Only one path is allowed')
        path = os.path.abspath(args.src)
    if not args.exact and len(args.scripts) > 1:
        raise RuntimeError('Two many entry scripts, only one is allowed')
    if not os.path.exists(path):
        raise RuntimeError('Not found source path: %s' % path)
    logging.info('Source path is "%s"', path)

    entries = [args.entry] if args.entry else args.scripts
    logging.info('Entry scripts are %s', entries)

    capsule = args.capsule if args.capsule else DEFAULT_CAPSULE
    if os.path.exists(capsule):
        logging.info('Use cached capsule %s', capsule)
    else:
        logging.info('Generate capsule %s', capsule)
        make_capsule(capsule)

    output = args.output
    if os.path.abspath(output) == path:
        raise RuntimeError('Output path can not be same as src')

    suffix = get_name_suffix() if args.enable_suffix else ''

    if args.recursive:
        logging.info('Search scripts mode: Recursive')
        pats = ['global-include *.py']

        if args.exclude:
            for item in args.exclude:
                for x in item.split(','):
                    if x.endswith('.py'):
                        logging.info('Exclude pattern "%s"', x)
                        pats.append('exclude %s' % x)
                    else:
                        logging.info('Exclude path "%s"', x)
                        pats.append('prune %s' % x)

        if os.path.abspath(output).startswith(path):
            x = os.path.abspath(output)[len(path):].strip('/\\')
            pats.append('prune %s' % x)
            logging.info('Auto exclude output path "%s"', x)

        if hasattr('', 'decode'):
            try:
                pats = [p.decode() for p in pats]
            except UnicodeDecodeError:
                pats = [p.decode('utf-8') for p in pats]

        files = Project.build_manifest(pats, path)

    elif args.exact:
        logging.info('Search scripts mode: Exact')
        files = [os.path.abspath(x) for x in args.scripts]

    else:
        logging.info('Search scripts mode: Normal')
        files = Project.build_globfiles(['*.py'], path)

    logging.info('Save obfuscated scripts to "%s"', output)
    if not os.path.exists(output):
        os.makedirs(output)

    logging.info('Read public key from capsule')
    prokey = get_product_key(capsule)

    cross_protection = 0 if args.no_cross_protection else \
        1 if args.cross_protection is None else args.cross_protection

    n = args.bootstrap_code
    relative = True if n == 3 else False if n == 2 else None
    bootstrap = (not args.no_bootstrap) and n
    elist = [os.path.abspath(x) for x in entries]

    logging.info('Obfuscate module mode is %s', args.obf_mod)
    logging.info('Obfuscate code mode is %s', args.obf_code)
    logging.info('Wrap mode is %s', args.wrap_mode)
    logging.info('Restrict mode is %d', restrict)
    logging.info('Advanced value is %d', advanced)
    logging.info('Super mode is %s', supermode)

    if args.no_runtime:
        if cross_protection == 1:
            logging.warning('No cross protection because no runtime generated')
            cross_protection = 0
    else:
        package = args.package_runtime
        licfile = args.license_file
        if (not restrict) and (not licfile):
            licfile = 'no-restrict'
        checklist = make_runtime(capsule, output, platforms=platforms,
                                 licfile=licfile, package=package,
                                 suffix=suffix, supermode=supermode)

        if cross_protection == 1:
            cross_protection = make_protection_code(
                (relative, checklist, suffix),
                multiple=len(platforms) > 1,
                supermode=supermode)

    logging.info('Start obfuscating the scripts...')
    adv_mode2 = (advanced - 2) if advanced > 2 else advanced
    for x in sorted(files):
        if os.path.isabs(x):
            a, b = x, os.path.join(output, os.path.basename(x))
        else:
            a, b = os.path.join(path, x), os.path.join(output, x)
        logging.info('\t%s -> %s', x, relpath(b))
        is_entry = os.path.abspath(a) in elist
        protection = is_entry and cross_protection
        plugins = search_plugins(args.plugins)

        d = os.path.dirname(b)
        if not os.path.exists(d):
            os.makedirs(d)

        adv_mode = adv_mode2 | (8 if is_entry else 0)
        encrypt_script(prokey, a, b, adv_mode=adv_mode, rest_mode=restrict,
                       protection=protection, platforms=platforms,
                       plugins=plugins, suffix=suffix, obf_code=args.obf_code,
                       obf_mod=args.obf_mod, wrap_mode=args.wrap_mode)

        if supermode:
            make_super_bootstrap(a, b, output, relative, suffix=suffix)
        elif is_entry and bootstrap:
            name = os.path.abspath(a)[len(path)+1:]
            make_entry(name, path, output, relative=relative, suffix=suffix)

    logging.info('Obfuscate %d scripts OK.', len(files))


@arcommand
def _check(args):
    '''Check consistency of project.'''
    project = Project()
    project.open(args.project)
    logging.info('Check project %s ...', args.project)
    project.check()
    logging.info('Check project OK.')


@arcommand
def _benchmark(args):
    '''Run benchmark test in current machine.'''
    logging.info('Python version: %d.%d', *sys.version_info[:2])
    logging.info('Start benchmark test ...')
    logging.info('Obfuscate module mode: %s', args.obf_mod)
    logging.info('Obfuscate code mode: %s', args.obf_code)
    logging.info('Obfuscate wrap mode: %s', args.wrap_mode)
    logging.info('Obfuscate advanced value: %s', args.adv_mode)

    logging.info('Benchmark bootstrap ...')
    path = os.path.normpath(os.path.dirname(__file__))
    p = subprocess.Popen(
        [sys.executable, 'benchmark.py', 'bootstrap', str(args.obf_mod),
         str(args.obf_code), str(args.wrap_mode), str(args.adv_mode)],
        cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    logging.info('Benchmark bootstrap OK.')

    logging.info('Run benchmark test ...')
    benchtest = os.path.join(path, '.benchtest')
    p = subprocess.Popen([sys.executable, 'benchmark.py'], cwd=benchtest)
    p.wait()

    if args.debug:
        logging.info('Test scripts are saved in the path: %s', benchtest)
    else:
        logging.info('Remove test path: %s', benchtest)
        shutil.rmtree(benchtest)

    logging.info('Finish benchmark test.')


@arcommand
def _hdinfo(args):
    print('')
    show_hd_info()


@arcommand
def _register(args):
    '''Make registration keyfile work, or show registration information.'''
    if args.filename is None:
        msg = _version_info(verbose=1)
        print(msg)
        if msg.find('Registration Code') > 0:
            print('')
            print('Please send request by this email if you would like to '
                  'change the registration information. Any issue feel free '
                  'to contact jondy.zhao@gmail.com')
        return

    logging.info('Start to register keyfile: %s', args.filename)
    register_keyfile(args.filename, legency=args.legency)
    logging.info('This keyfile has been registered successfully.')
    logging.info('Run "pyarmor register" to check registration information.')


@arcommand
def _download(args):
    '''List and download platform-dependent dynamic libraries.'''
    if args.platname:
        logging.info('Downloading dynamic library for %s', args.platname)
        download_pytransform(args.platname, output=args.output, url=args.url)

    elif args.update is not None:
        update_pytransform(args.update)

    else:
        lines = []
        plist = get_platform_list()
        patterns = args.pattern.split('.') if args.pattern else []
        if patterns:
            logging.info('Search the available libraries for %s:', patterns)
        else:
            if args.pattern is None:
                if args.help_platform is None:
                    args.help_platform = ''
            else:
                logging.info('All the available libraries:')
        help_platform = args.help_platform
        if help_platform is not None:
            patterns = help_platform.split('.') if help_platform else []
            if patterns:
                logging.info('All available platform names for %s:', patterns)
            else:
                logging.info('All available standard platform names:')

        def match_platform(item):
            for pat in patterns:
                if (pat not in item['id'].split('.')) and \
                   (pat != item['platform']) and \
                   (pat not in item['machines']) and \
                   (pat not in item['features']):
                    return False
            return True

        for p in plist:
            if not match_platform(p):
                continue

            if help_platform is not None:
                pname = '\t ' + p['name']
                if pname not in lines:
                    lines.append(pname)
                continue

            lines.append('')
            lines.append('%16s: %s' % ('id', p['id']))
            lines.append('%16s: %s' % ('name', p['name']))
            lines.append('%16s: %s' % ('platform', p['platform']))
            lines.append('%16s: %s' % ('machines', ', '.join(p['machines'])))
            lines.append('%16s: %s' % ('features', ', '.join(p['features'])))
            lines.append('%16s: %s' % ('remark', p['remark']))

        if help_platform is not None:
            lines.sort()
        logging.info('\n%s', '\n'.join(lines))


@arcommand
def _runtime(args):
    '''Generate runtime package separately.'''
    capsule = DEFAULT_CAPSULE
    name = 'pytransform_bootstrap'
    output = os.path.join(args.output, name) if args.inside else args.output
    package = not args.no_package
    suffix = get_name_suffix() if args.enable_suffix else ''
    licfile = 'no' if args.no_license else args.license_file
    supermode = args.super_mode or (args.advanced in (2, 4))
    vmode = args.vm_mode or (args.advanced in (3, 4))
    platforms = compatible_platform_names(args.platforms)
    platforms = check_cross_platform(platforms, supermode, vmode=vmode)
    if platforms is False:
        return

    checklist = make_runtime(capsule, output, licfile=licfile,
                             platforms=platforms, package=package,
                             suffix=suffix, supermode=supermode)

    logging.info('Generating protection script ...')
    filename = os.path.join(output, 'pytransform_protection.py')
    data = make_protection_code((args.inside, checklist, suffix),
                                multiple=len(platforms) > 1,
                                supermode=args.super_mode)
    with open(filename, 'w') as f:
        f.write(data)

    if not args.super_mode:
        filename = os.path.join(output, '__init__.py') if args.inside else \
            os.path.join(args.output, name + '.py')
        logging.info('Generating bootstrap script ...')
        make_bootstrap_script(filename, capsule=capsule, suffix=suffix)
        logging.info('Generating bootstrap script %s OK', filename)


def _version_action():
    pytransform_bootstrap()
    return _version_info()


def _version_info(verbose=2):
    rcode = get_registration_code()
    if rcode:
        rcode = rcode.replace('-sn-1.txt', '')
        ver = 'PyArmor Version %s' % version
    else:
        ver = 'PyArmor Trial Version %s' % version
    if verbose == 0:
        return ver

    info = [ver]
    if rcode:
        info.append('Registration Code: %s' % rcode)
        info.append(query_keyinfo(rcode))
    if verbose > 1:
        info.extend(['', version_info])
    return '\n'.join(info)


def _parser():
    parser = argparse.ArgumentParser(
        prog='pyarmor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
        epilog='See "pyarmor <command> -h" for more information '
               'on a specific command.\n\nMore usage refer to '
               'https://pyarmor.readthedocs.io'
    )
    parser.add_argument('-v', '--version', action='version',
                        version=_version_action)
    parser.add_argument('-q', '--silent', action='store_true',
                        help='Suppress all normal output')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Print exception traceback and debugging message')
    parser.add_argument('--home', help='Change pyarmor home path')
    parser.add_argument('--boot', help='Change boot platform')

    subparsers = parser.add_subparsers(
        title='The most commonly used pyarmor commands are',
        metavar=''
    )

    #
    # Command: obfuscate
    #
    cparser = subparsers.add_parser(
        'obfuscate',
        aliases=['o'],
        epilog=_obfuscate.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Obfuscate python scripts')
    cparser.add_argument('-O', '--output', default='dist', metavar='PATH',
                         help='Output path, default is "%(default)s"')
    cparser.add_argument('-r', '--recursive', action='store_true',
                         help='Search scripts in recursive mode')
    cparser.add_argument('--exclude', metavar='PATH', action='append',
                         help='Exclude the path in recursive mode. '
                         'Multiple paths are allowed, separated by ",". '
                         'Or use this option multiple times')
    cparser.add_argument('--exact', action='store_true',
                         help='Only obfusate list scripts')
    cparser.add_argument('--no-bootstrap', action='store_true',
                         help='Do not insert bootstrap code to entry script')
    cparser.add_argument('--bootstrap', '--bootstrap-code',
                         dest='bootstrap_code',
                         type=int, default=1, choices=(0, 1, 2, 3),
                         help='How to insert bootstrap code to entry script')
    cparser.add_argument('scripts', metavar='SCRIPT', nargs='+',
                         help='List scripts to obfuscated, the first script '
                         'is entry script')
    cparser.add_argument('-s', '--src', metavar='PATH',
                         help='Specify source path if entry script is not '
                         'in the top most path')
    cparser.add_argument('-e', '--entry', metavar='SCRIPT',
                         help=argparse.SUPPRESS)
    cparser.add_argument('--plugin', dest='plugins', metavar='NAME',
                         action='append',
                         help='Insert extra code to entry script, '
                         'it could be used multiple times')
    cparser.add_argument('--restrict', type=int, choices=range(5),
                         default=1, help='Set restrict mode')
    cparser.add_argument('--capsule', help=argparse.SUPPRESS)
    cparser.add_argument('--platform', dest='platforms', metavar='NAME',
                         action='append',
                         help='Target platform to run obfuscated scripts, '
                         'use this option multiple times for more platforms')
    cparser.add_argument('--obf-mod', type=int, choices=(0, 1, 2), default=2)
    cparser.add_argument('--obf-code', type=int, choices=(0, 1, 2), default=1)
    cparser.add_argument('--wrap-mode', type=int, choices=(0, 1), default=1)
    cparser.add_argument('--advanced', type=int, choices=(0, 1, 2, 3, 4),
                         default=0, help='Enable advanced mode or super mode')
    cparser.add_argument('--package-runtime', type=int, default=1,
                         choices=(0, 1), help='Package runtime files or not')
    cparser.add_argument('-n', '--no-runtime', action='store_true',
                         help='DO NOT generate runtime files')
    cparser.add_argument('--enable-suffix', action='store_true',
                         help='Make unique runtime files and bootstrap code')
    cparser.add_argument('--with-license', dest='license_file',
                         help='Use this license file other than default')
    group = cparser.add_mutually_exclusive_group()
    group.add_argument('--no-cross-protection', action='store_true',
                       help='Do not insert protection code to entry script')
    group.add_argument('--cross-protection', metavar='SCRIPT',
                       help='Specify cross protection script')

    cparser.set_defaults(func=_obfuscate)

    #
    # Command: license
    #
    cparser = subparsers.add_parser(
        'licenses',
        aliases=['l'],
        epilog=_licenses.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Generate new licenses for obfuscated scripts'
    )
    cparser.add_argument('codes', nargs='*', metavar='CODE',
                         help='Registration code for this license')
    group = cparser.add_argument_group('Bind license to hardware')
    group.add_argument('-e', '--expired', metavar='YYYY-MM-DD',
                       help='Expired date for this license')
    group.add_argument('-d', '--bind-disk', metavar='SN',
                       help='Bind license to serial number of harddisk')
    group.add_argument('-4', '--bind-ipv4', metavar='a.b.c.d',
                       help='Bind license to ipv4 addr')
    # group.add_argument('-6', '--bind-ipv6', metavar='a:b:c:d',
    #                    help='Bind license to ipv6 addr')
    group.add_argument('-m', '--bind-mac', metavar='x:x:x:x',
                       help='Bind license to mac addr')
    group.add_argument('-x', '--bind-data', metavar='DATA', help='Pass extra '
                       'data to license, used to extend license type')
    group.add_argument('--bind-domain', metavar='DOMAIN',
                       help='Bind license to domain name')
    group.add_argument('--bind-file', metavar='filename',
                       help=argparse.SUPPRESS)
    group.add_argument('--fixed',
                       help='Bind license to python dynamic library')
    cparser.add_argument('-P', '--project', default='', help=argparse.SUPPRESS)
    cparser.add_argument('-C', '--capsule', help=argparse.SUPPRESS)
    cparser.add_argument('-O', '--output', help='Output path, default is '
                         '`licenses` (`stdout` is also supported)')
    cparser.add_argument('--disable-restrict-mode', action='store_true',
                         help='Disable all the restrict modes')
    cparser.add_argument('--enable-period-mode', action='store_true',
                         help='Check license periodly (per hour)')
    cparser.add_argument('--restrict', type=int, choices=(0, 1),
                         default=1, help=argparse.SUPPRESS)

    cparser.set_defaults(func=_licenses)

    #
    # Command: pack
    #
    cparser = subparsers.add_parser(
        'pack',
        aliases=['p'],
        epilog=packer.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Pack obfuscated scripts to one bundle'
    )
    packer.add_arguments(cparser)
    cparser.set_defaults(func=packer.packer)

    #
    # Command: init
    #
    cparser = subparsers.add_parser(
        'init',
        aliases=['i'],
        epilog=_init.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Create a project to manage obfuscated scripts'
    )
    cparser.add_argument('-t', '--type', default='auto',
                         choices=('auto', 'app', 'pkg'))
    cparser.add_argument('-e', '--entry',
                         help='Entry script of this project')
    cparser.add_argument('-s', '--src', default='',
                         help='Project src, base path for matching scripts')
    cparser.add_argument('--capsule', help=argparse.SUPPRESS)
    cparser.add_argument('project', nargs='?', default='', help='Project path')
    cparser.set_defaults(func=_init)

    #
    # Command: config
    #
    cparser = subparsers.add_parser(
        'config',
        aliases=['c'],
        epilog=_config.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Update project settings')
    cparser.add_argument('project', nargs='?', metavar='PATH',
                         default='', help='Project path')
    cparser.add_argument('--name')
    cparser.add_argument('--title')
    cparser.add_argument('--src',
                         help='Project src, base path for matching scripts')
    cparser.add_argument('--output',
                         help='Output path for obfuscated scripts')
    cparser.add_argument('--capsule', help=argparse.SUPPRESS)
    cparser.add_argument('--platform', dest='platforms', metavar='NAME',
                         action='append',
                         help='Target platform to run obfuscated scripts, '
                         'use this option multiple times for more platforms')
    cparser.add_argument('--manifest', metavar='TEMPLATE',
                         help='Filter the project scritps by these manifest '
                         'template commands')
    cparser.add_argument('--entry', metavar='SCRIPT',
                         help='Entry script of this project, sperated by "," '
                         'for multiple entry scripts')
    cparser.add_argument('--is-package', type=int, choices=(0, 1))
    cparser.add_argument('--disable-restrict-mode', type=int, choices=(0, 1),
                         help=argparse.SUPPRESS)
    cparser.add_argument('--restrict', '--restrict-mode', dest='restrict_mode',
                         type=int, choices=range(5),
                         help='Set restrict mode')
    cparser.add_argument('--obf-module-mode', choices=Project.OBF_MODULE_MODE,
                         help=argparse.SUPPRESS)
    cparser.add_argument('--obf-code-mode', choices=Project.OBF_CODE_MODE,
                         help=argparse.SUPPRESS)
    cparser.add_argument('--obf-mod', type=int, choices=(0, 1, 2))
    cparser.add_argument('--obf-code', type=int, choices=(0, 1, 2))
    cparser.add_argument('--wrap-mode', type=int, choices=(0, 1))
    cparser.add_argument('--cross-protection', type=int, choices=(0, 1),
                         help='Insert cross protection code to entry script '
                         'or not')
    cparser.add_argument('--bootstrap', '--bootstrap-code', type=int,
                         dest='bootstrap_code', choices=(0, 1, 2, 3),
                         help='How to insert bootstrap code to entry script')
    cparser.add_argument('--runtime-path', metavar="RPATH",
                         help='The path to search dynamic library in runtime, '
                         'if it is not within the runtime package')
    cparser.add_argument('--plugin', dest='plugins', metavar='NAME',
                         action='append',
                         help='Insert extra code to entry script, '
                         'it could be used multiple times')
    cparser.add_argument('--advanced', '--advanced-mode', dest='advanced_mode',
                         type=int, choices=(0, 1, 2, 3, 4),
                         help='Enable advanced mode or super mode')
    cparser.add_argument('--package-runtime', choices=(0, 1), type=int,
                         help='Package runtime files or not')
    cparser.add_argument('--enable-suffix', type=int, choices=(0, 1),
                         help='Make unique runtime files and bootstrap code')
    cparser.add_argument('--with-license', dest='license_file',
                         help='Use this license file other than default')
    # cparser.add_argument('--reset', choices=('all', 'glob', 'exact'),
    #                      help='Initialize project scripts by different way')
    # cparser.add_argument('--exclude', dest="exludes", action="append",
    #                      help='Exclude the path or script from project. '
    #                      'This option could be used multiple times')
    cparser.set_defaults(func=_config)

    #
    # Command: build
    #
    cparser = subparsers.add_parser(
        'build',
        aliases=['b'],
        epilog=_build.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Obfuscate all the scripts in the project')
    cparser.add_argument('project', nargs='?', metavar='PATH', default='',
                         help='Project path, or project configuratioin file')
    cparser.add_argument('-B', '--force', action='store_true',
                         help='Force to obfuscate all scripts, otherwise '
                         'only obfuscate the changed scripts since last build')
    cparser.add_argument('-r', '--only-runtime', action='store_true',
                         help='Generate runtime files only')
    cparser.add_argument('-n', '--no-runtime', action='store_true',
                         help='DO NOT generate runtime files')
    cparser.add_argument('-O', '--output',
                         help='Output path, override project configuration')
    cparser.add_argument('--platform', dest='platforms', metavar='NAME',
                         action='append',
                         help='Target platform to run obfuscated scripts, '
                         'use this option multiple times for more platforms')
    cparser.add_argument('--package-runtime', choices=(0, 1), type=int,
                         help='Package runtime files or not')
    cparser.add_argument('--with-license', dest='license_file',
                         help='Use this license file other than default')
    cparser.set_defaults(func=_build)

    #
    # Command: info
    #
    cparser = subparsers.add_parser(
        'info',
        epilog=_info.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Show project information'
    )
    cparser.add_argument('project', nargs='?', metavar='PATH',
                         default='', help='Project path')
    cparser.set_defaults(func=_info)

    #
    # Command: check
    #
    cparser = subparsers.add_parser(
        'check',
        epilog=_check.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Check consistency of project')
    cparser.add_argument('project', nargs='?', metavar='PATH',
                         default='', help='Project path')
    cparser.set_defaults(func=_check)

    #
    # Command: hdinfo
    #
    cparser = subparsers.add_parser(
        'hdinfo',
        epilog=_hdinfo.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Show hardware information'
    )
    cparser.set_defaults(func=_hdinfo)

    #
    # Command: benchmark
    #
    cparser = subparsers.add_parser(
        'benchmark',
        epilog=_benchmark.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Run benchmark test in current machine'
    )
    cparser.add_argument('-m', '--obf-mod', choices=(0, 1, 2),
                         default=2, type=int)
    cparser.add_argument('-c', '--obf-code', choices=(0, 1, 2),
                         default=1, type=int)
    cparser.add_argument('-w', '--wrap-mode', choices=(0, 1),
                         default=1, type=int)
    cparser.add_argument('-a', '--advanced', choices=(0, 1, 2, 3, 4),
                         default=0, dest='adv_mode', type=int)
    cparser.add_argument('-d', '--debug', action='store_true',
                         help='Do not clean the test scripts'
                              'generated in real time')
    cparser.set_defaults(func=_benchmark)

    #
    # Command: capsule
    #
    cparser = subparsers.add_parser(
        'capsule',
        epilog=_capsule.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    cparser.add_argument('-f', '--force', action='store_true',
                         help='Force update public capsule even if it exists')
    cparser.add_argument('path', nargs='?', default=os.path.expanduser('~'),
                         help='Path to save capsule, default is home path')
    cparser.set_defaults(func=_capsule)

    #
    # Command: register
    #
    cparser = subparsers.add_parser(
        'register',
        epilog=_register.__doc__ + purchase_info,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Make registration keyfile work')
    cparser.add_argument('-n', '--legency', action='store_true',
                         help='Store `license.lic` in the traditional way')
    cparser.add_argument('filename', nargs='?', metavar='KEYFILE',
                         help='Filename of registration keyfile')
    cparser.set_defaults(func=_register)

    #
    # Command: download
    #
    cparser = subparsers.add_parser(
        'download',
        epilog=_download.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Download platform-dependent dynamic libraries')
    cparser.add_argument('-O', '--output', metavar='PATH',
                         help='Save downloaded library to this path, default '
                         'is `~/.pyarmor/platforms`')
    cparser.add_argument('--url', help=argparse.SUPPRESS)
    group = cparser.add_mutually_exclusive_group()
    group.add_argument('--help-platform', nargs='?', const='',
                       metavar='FILTER',
                       help='Display all available platform names')
    group.add_argument('-L', '--list', nargs='?', const='',
                       dest='pattern', metavar='FILTER',
                       help='List available dynamic libraries in details')
    group.add_argument('-u', '--update', nargs='?', const='*', metavar='NAME',
                       help='Update all the downloaded dynamic libraries')
    group.add_argument('platname', nargs='?', metavar='NAME',
                       help='Download dynamic library for this platform')
    cparser.set_defaults(func=_download)

    #
    # Command: runtime
    #
    cparser = subparsers.add_parser(
        'runtime',
        epilog=_runtime.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help='Generate runtime package separately')
    cparser.add_argument('-O', '--output', metavar='PATH', default='dist',
                         help='Output path, default is "%(default)s"')
    cparser.add_argument('-n', '--no-package', action='store_true',
                         help='Generate runtime files without package')
    cparser.add_argument('-i', '--inside', action='store_true',
                         help='Generate bootstrap script which is used '
                         'inside one package')
    cparser.add_argument('-L', '--with-license', metavar='FILE',
                         dest='license_file',
                         help='Replace default license with this file')
    cparser.add_argument('--without-license', dest='no_license',
                         action='store_true', help=argparse.SUPPRESS)
    cparser.add_argument('--platform', dest='platforms', metavar='NAME',
                         action='append',
                         help='Generate runtime package for this platform, '
                         'use this option multiple times for more platforms')
    cparser.add_argument('--enable-suffix', action='store_true',
                         help='Make unique runtime files and bootstrap code')
    cparser.add_argument('--super-mode', action='store_true',
                         help='Enable super mode')
    cparser.add_argument('--vm-mode', action='store_true',
                         help='Enable vm protection mode')
    cparser.add_argument('--advanced', type=int, choices=(2, 4),
                         help=argparse.SUPPRESS)
    cparser.add_argument('pkgname', nargs='?', default='pytransform',
                         help=argparse.SUPPRESS)
    cparser.set_defaults(func=_runtime)

    return parser


def excepthook(type, value, traceback):
    logging.error('%s', value)
    sys.exit(1)


def _change_home_path(path):
    if not os.path.exists(path):
        raise RuntimeError('Home path does not exists')

    import utils
    home = os.path.abspath(path)
    utils.PYARMOR_HOME = utils.HOME_PATH = home
    utils.CROSS_PLATFORM_PATH = os.path.join(home, 'platforms')
    utils.DEFAULT_CAPSULE = os.path.join(home, capsule_filename)
    utils.OLD_CAPSULE = os.path.join(home, '..', capsule_filename)
    if not os.getenv('PYARMOR_HOME', home) == home:
        raise RuntimeError('The option --home conflicts with PYARMOR_HOME')
    os.environ['PYARMOR_HOME'] = home

    licfile = os.path.join(home, 'license.lic')
    if os.path.exists(licfile):
        logging.info('Copy %s to %s', licfile, PYARMOR_PATH)
        shutil.copy(licfile, PYARMOR_PATH)


def _clean_home_path():
    licfile = os.path.join(PYARMOR_PATH, 'license.lic')
    if os.path.exists(licfile):
        logging.info('Clean unused license file: %s', licfile)
        os.remove(licfile)


def main(argv):
    parser = _parser()
    args = parser.parse_args(argv)
    if not hasattr(args, 'func'):
        parser.print_help()
        return

    if args.silent:
        logging.getLogger().setLevel(100)
    if args.debug or sys.flags.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        sys._debug_pyarmor = True
    elif os.path.basename(sys.argv[0]).split('.')[0] == 'pyarmor':
        sys.excepthook = excepthook

    if args.home:
        logging.info('Set pyarmor home path: %s', args.home)
        _change_home_path(args.home)
    else:
        _clean_home_path()

    if args.boot:
        logging.info('Set boot platform: %s', args.boot)
        os.environ['PYARMOR_PLATFORM'] = args.boot

    if not args.func.__name__[1:] in ('download', 'register'):
        pytransform_bootstrap(capsule=DEFAULT_CAPSULE, force=args.boot)

    logging.info(_version_info(verbose=0))
    args.func(args)


def main_entry():
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)-8s %(message)s',
    )
    main(sys.argv[1:])


if __name__ == '__main__':
    main_entry()
