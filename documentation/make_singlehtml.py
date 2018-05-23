import subprocess

def _CMD(cmd):
    print('CMD(cmd={})'.format(cmd))
    res = subprocess.getoutput(cmd.split(' '))

    # print('res=', res)
    # print('type(res)=', type(res))
    return res

res = _CMD(r'C:\Users\gmiller\PycharmProjects\tcp-connection-handler\documentation\make singlehtml')
print('res=', res)