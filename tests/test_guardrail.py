import pytest
from harness.guardrail import check, GuardrailResult
from harness.models import Action


def _act(payload: str, type_: str = "shell") -> Action:
    return Action(type=type_, payload=payload)


# BLOCK tests
def test_block_rm_rf_root():
    assert check(_act("rm -rf /")) == GuardrailResult.BLOCK


def test_block_rm_rf_home():
    assert check(_act("rm -rf ~")) == GuardrailResult.BLOCK


def test_block_fork_bomb():
    assert check(_act(":(){ :|:& };:")) == GuardrailResult.BLOCK


def test_block_dd():
    assert check(_act("dd if=/dev/zero of=/dev/sda")) == GuardrailResult.BLOCK


def test_block_mkfs():
    assert check(_act("mkfs.ext4 /dev/sdb")) == GuardrailResult.BLOCK


def test_block_write_etc():
    assert check(_act("echo x > /etc/passwd", "run_code")) == GuardrailResult.BLOCK


def test_block_write_sys():
    assert check(_act("open('/sys/foo', 'w')", "run_code")) == GuardrailResult.BLOCK


def test_block_write_proc():
    assert check(_act("open('/proc/1/mem', 'w')", "run_code")) == GuardrailResult.BLOCK


# HITL tests
def test_hitl_os_remove():
    assert check(_act("os.remove('/tmp/f')", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_shutil_rmtree():
    assert check(_act("shutil.rmtree('/home/user/data')", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_subprocess_run():
    assert check(_act("subprocess.run(['ls'])", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_os_system():
    assert check(_act("os.system('ls')", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_eval():
    assert check(_act("eval('1+1')", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_exec():
    assert check(_act("exec('pass')", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_socket_connect():
    assert check(_act("s.connect(('8.8.8.8', 53))", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_urllib_urlopen():
    assert check(_act("urllib.request.urlopen('http://x.com')", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_requests_get():
    assert check(_act("requests.get('http://x.com')", "run_code")) == GuardrailResult.HITL_REQUIRED


def test_hitl_requests_post():
    assert check(_act("requests.post('http://x.com', data={})", "run_code")) == GuardrailResult.HITL_REQUIRED


# ALLOW tests
def test_allow_safe_code():
    assert check(_act("print('hello')", "run_code")) == GuardrailResult.ALLOW


def test_allow_math():
    assert check(_act("x = 1 + 2; print(x)", "run_code")) == GuardrailResult.ALLOW


def test_allow_import_os_without_dangerous_call():
    assert check(_act("import os\nprint(os.getcwd())", "run_code")) == GuardrailResult.ALLOW


def test_block_takes_priority_over_hitl():
    assert check(_act("rm -rf / && eval('x')")) == GuardrailResult.BLOCK


def test_guardrail_result_enum_values():
    assert GuardrailResult.ALLOW.value == "ALLOW"
    assert GuardrailResult.BLOCK.value == "BLOCK"
    assert GuardrailResult.HITL_REQUIRED.value == "HITL_REQUIRED"
